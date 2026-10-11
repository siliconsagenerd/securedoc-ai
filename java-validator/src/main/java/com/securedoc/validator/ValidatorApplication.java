package com.securedoc.validator;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** Entry point for the SecureDoc AI document-validation service. */
@SpringBootApplication
public class ValidatorApplication {

    public static void main(String[] args) {
        SpringApplication.run(ValidatorApplication.class, args);
    }
}
