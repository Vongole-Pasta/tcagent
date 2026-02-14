
import logging
import json
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser

from config import Config
from infra.db_client import DBClient
from core.agent.state import AgentState, TargetMethod, TraceResult, GeneratedScenario
from core.agent.prompts import SCENARIO_GENERATION_PROMPT

logger = logging.getLogger(__name__)

class IntegratedTestAgentNodes:
    def __init__(self, db_client: DBClient):
        self.db_client = db_client
        self.llm = ChatOpenAI(
            model=Config.MODEL_NAME,
            temperature=0,
            api_key=Config.OPENAI_API_KEY
        )

    def identify_targets(self, state: AgentState) -> Dict[str, Any]:
        """
        Identify methods that have been modified or are new.
        """
        logger.info("Identifying target methods (NEW/MODIFIED)...")
        query = """
        MATCH (m:METHOD)
        WHERE m.status IN ['NEW', 'MODIFIED']
        OPTIONAL MATCH (m)<-[:CONTAINS]-(c:TYPE)<-[:CONTAINS]-(f:FILE)
        RETURN elementId(m) as id, m.name as name, m.signature as signature, m.status as status, f.path as file_path
        """
        results = self.db_client.execute_query(query)
        
        targets = []
        for row in results:
            targets.append(TargetMethod(
                id=row['id'],
                name=row['name'],
                signature=row['signature'],
                status=row['status'],
                file_path=row.get('file_path', 'UNKNOWN')
            ))
            
        logger.info(f"Found {len(targets)} target methods.")
        return {"target_methods": targets}

    def trace_roots(self, state: AgentState) -> Dict[str, Any]:
        """
        Trace back to the root methods (entry points) that call the target methods.
        """
        targets = state.target_methods
        trace_results = []
        
        logger.info(f"Tracing roots for {len(targets)} targets...")
        
        # Dictionary to group traces by root_method_id
        # Key: root_method_id, Value: TraceResult
        grouped_traces: Dict[str, TraceResult] = {}
        
        for target in targets:
            # Find root methods (methods that are not called by any other method in the project context)
            # OR methods that are explicitly Controller endpoints (if discernible).
            # For simplicity, we find the longest upstream paths.
            query = """
            MATCH path = (root:METHOD)-[:CALLS*0..]->(target:METHOD)
            WHERE (elementId(target) = $target_id)
              AND NOT ()-[:CALLS]->(root)
            RETURN root, target, [n in nodes(path) | n.signature] as call_path
            LIMIT 5
            """
            
            paths = self.db_client.execute_query(query, {"target_id": target.id})
            
            for row in paths:
                root_node = row['root']
                target_node = row['target']
                call_path = row['call_path']
                root_id = root_node.element_id
                
                # Create AffectedMethod object
                affected_method = {
                    "id": target_node.element_id,
                    "signature": target_node.get('signature', ''),
                    "code": target_node.get('source', ''),
                    "call_path": call_path
                }

                if root_id in grouped_traces:
                    # Add to existing trace if unique
                    existing = grouped_traces[root_id]
                    if not any(am['id'] == affected_method['id'] for am in existing.affected_methods):
                        existing.affected_methods.append(affected_method)
                else:
                    # Fetch parameters for the root method context (only once per root)
                    param_query = """
                    MATCH (m:METHOD)-[:CONTAINS]->(p:PARAMETER)
                    WHERE elementId(m) = $root_id
                    OPTIONAL MATCH (p)-[:OF_TYPE]->(t:TYPE)
                    OPTIONAL MATCH (t)-[:CONTAINS]->(f:FIELD)
                    RETURN p.index as param_index, p.name as param_name, p.type as param_type, t.name as type_name, collect({name: f.name, type: f.type}) as fields
                    ORDER BY param_index
                    """
                    params_result = self.db_client.execute_query(param_query, {"root_id": root_id})
                    
                    parameter_infos = []
                    for p_row in params_result:
                        # Filter out fields with None values (artifacts of OPTIONAL MATCH)
                        raw_fields = p_row['fields']
                        clean_fields = [f for f in raw_fields if f.get('name') is not None and f.get('type') is not None]
                        
                        parameter_infos.append({
                            "name": p_row['param_name'],
                            "type": p_row['param_type'],
                            "fields": clean_fields
                        })

                    grouped_traces[root_id] = TraceResult(
                        root_method_id=root_id,
                        root_method_signature=root_node.get('signature', ''),
                        root_method_code=root_node.get('source', ''),
                        affected_methods=[affected_method],
                        parameters=parameter_infos
                    )

        trace_results = list(grouped_traces.values())
        logger.info(f"Traced {len(trace_results)} unique root paths covering multiple targets.")
        return {"trace_results": trace_results}

    def generate_scenarios(self, state: AgentState) -> Dict[str, Any]:
        """
        Generate test scenarios using LLM based on grouped trace results.
        """
        traces = state.trace_results
        generated_scenarios = []
        
        logger.info(f"Generating scenarios for {len(traces)} root groups...")
        
        parser = JsonOutputParser()
        chain = SCENARIO_GENERATION_PROMPT | self.llm | parser
        
        for i, trace in enumerate(traces):
            try:
                # Format affected methods context
                affected_methods_context = ""
                for idx, am in enumerate(trace.affected_methods):
                    affected_methods_context += f"""
--- Target Method {idx+1} ---
Signature: {am.signature}
Call Path: {" -> ".join(am.call_path)}
Code:
{am.code[:2000]}...
"""
                
                # Prepare input for LLM
                inputs = {
                    "root_method": f"Signature: {trace.root_method_signature}\nCode:\n{trace.root_method_code[:2000]}...",
                    "affected_methods_context": affected_methods_context,
                    "parameters": json.dumps([p.model_dump() for p in trace.parameters], indent=2, ensure_ascii=False)
                }
                
                result = chain.invoke(inputs)
                
                # Parse result into GeneratedScenario objects
                if isinstance(result, list):
                    for item in result:
                        scenario = GeneratedScenario(
                            test_case_id=f"TC-{len(generated_scenarios)+1:03d}",
                            test_case_name=item.get('test_case_name', 'No Name'),
                            step_no=item.get('step_no', 1),
                            description=item.get('description', ''),
                            pre_condition=item.get('pre_condition', ''),
                            procedure=item.get('procedure', ''),
                            expected_result=item.get('expected_result', ''),
                            scenario_id=f"SC-{i+1:03d}", # Same Scenario ID for same Root group
                            root_method_signature=trace.root_method_signature
                        )
                        generated_scenarios.append(scenario)
                
                logger.info(f"Generated scenarios for root group {i+1}/{len(traces)}")
                
            except Exception as e:
                logger.error(f"Failed to generate scenario for trace {i}: {e}")
                return {"generated_scenarios": generated_scenarios, "errors": [f"Scenario gen error: {e}"]}

        return {"generated_scenarios": generated_scenarios}
