package com.example.test;

import java.util.List;
import java.util.Map;

public class GenericTestDto {
    private List<UserDto> users;
    private Map<String, Product> productCache;

    private UserDto[] userArray; // Array
    private List<? extends Product> productList; // Wildcard

    public void processUsers(List<UserDto> userList) {
        // ...
    }

    public void processVarargs(UserDto... users) { // Varargs
        // ...
    }
}
