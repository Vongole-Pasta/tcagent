
import logging
import openpyxl
from openpyxl import Workbook
from typing import List, Optional
from core.agent.state import GeneratedScenario

logger = logging.getLogger(__name__)

class ExcelExporter:
    @staticmethod
    def create_workbook(scenarios: List[GeneratedScenario], summary: Optional[str], file_path: str):
        """
        Create an Excel workbook with 'Summary', 'VOD', and 'Scenario' sheets.
        """
        wb = Workbook()
        
        # --- Summary Sheet ---
        if summary:
            ws_summary = wb.active
            ws_summary.title = "Summary"
            ws_summary["A1"] = "Test Strategy Summary"
            ws_summary["A2"] = summary
            # Simple styling if needed, e.g., alignment
            
            # Create VOD sheet as the second sheet
            ws_vod = wb.create_sheet("VOD")
        else:
            ws_vod = wb.active
            ws_vod.title = "VOD"
        
        # Headers (Row 4 based on analysis, but we'll start at 1 for simplicity unless template is required)
        # User analysis showed headers at row ~4. Let's stick to a clean new file for now.
        headers_vod = [
            "Test Case ID", "Test Case Name", "Step No", "Description", 
            "Pre-condition", "Procedure", "Expected Result", "", "", "", "", "", "", "", "", "", "Scenario ID"
        ]
        ws_vod.append(headers_vod)
        
        for scenario in scenarios:
            row = [
                scenario.test_case_id,          # 1
                scenario.test_case_name,        # 2
                scenario.step_no,               # 3
                scenario.description,           # 4
                scenario.pre_condition,         # 5
                scenario.procedure,             # 6
                scenario.expected_result,       # 7
                "", "", "", "", "", "", "", "", "", # 8-16 (Empty)
                scenario.scenario_id            # 17
            ]
            ws_vod.append(row)

        # --- Scenario Sheet ---
        ws_scenario = wb.create_sheet("시나리오")
        headers_scenario = ["Scenario ID", "Func Name", "Description"]
        ws_scenario.append(headers_scenario)
        
        # Unique scenarios
        seen_scenarios = set()
        for scenario in scenarios:
            if scenario.scenario_id not in seen_scenarios:
                ws_scenario.append([
                    scenario.scenario_id,
                    scenario.test_case_name, # Approximation
                    scenario.description     # Approximation
                ])
                seen_scenarios.add(scenario.scenario_id)
        
        try:
            wb.save(file_path)
            logger.info(f"Excel file saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save Excel file: {e}")
            raise

