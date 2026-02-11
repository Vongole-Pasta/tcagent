package com.example.test;

import java.util.List;
import java.util.Map;

public class GenericTestDto {
    private List<UserDto> users;
    private Map<String, Product> productCache;

    public void processUsers(List<UserDto> userList) {
        // ...
    }
}
