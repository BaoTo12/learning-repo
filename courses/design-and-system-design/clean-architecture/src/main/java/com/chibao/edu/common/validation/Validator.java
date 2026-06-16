package com.chibao.edu.common.validation;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;

import java.util.Set;
import static jakarta.validation.Validation.buildDefaultValidatorFactory;

public class Validator {
    private final static jakarta.validation.Validator validator =
            buildDefaultValidatorFactory().getValidator();


    public static <T> void validate(T subject) {
        Set<ConstraintViolation<T>> violations = validator.validate(subject);
        if (!violations.isEmpty()) {
            throw new ConstraintViolationException(violations);
        }
    }
}
