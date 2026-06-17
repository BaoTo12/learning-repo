package com.chibao.mongodblearning.validation;

import com.mongodb.client.MongoDatabase;
import com.mongodb.client.model.CreateCollectionOptions;
import com.mongodb.client.model.ValidationOptions;
import org.bson.Document;

import java.util.List;

public class ComplexSchemaValidation {
    public void setupValidatedCollection(MongoDatabase database) {
        Document properties = new Document()
                // 1. String with Pattern Validation (Email Regex)
                .append("email", new Document("bsonType", "string")
                        .append("pattern", "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
                )
                // 2. Enum Constraint (Fixed set of valid strings)
                .append("role", new Document("bsonType", "string")
                        .append("enum", List.of("STUDENT", "INSTRUCTOR", "ADMIN"))
                )
                // 3. Numeric Boundaries (GPA must be between 0.0 and 4.0)
                .append("gpa", new Document("bsonType", "double")
                        .append("minimum", 0.0)
                        .append("maximum", 4.0)
                )
                // 4. Nested Object Validation
                .append("profile", new Document("bsonType", "object")
                        .append("required", List.of("firstName", "lastName"))
                        .append("properties", new Document()
                                .append("firstName", new Document("bsonType", "string"))
                                .append("lastName", new Document("bsonType", "string"))
                        )
                )
                // 5. Array Validation (List of unique strings)
                .append("skills", new Document("bsonType", "array")
                        .append("uniqueItems", true)
                        .append("items", new Document("bsonType", "string"))
                );

        Document schema = new Document("bsonType", "object")
                .append("required", List.of("email", "role", "gpa"))
                .append("properties", properties);

        ValidationOptions vOpts = new ValidationOptions()
                .validator(new Document("$jsonSchema", schema))
                .validationAction(com.mongodb.client.model.ValidationAction.ERROR)
                .validationLevel(com.mongodb.client.model.ValidationLevel.STRICT);

        database.createCollection("students", new CreateCollectionOptions().validationOptions(vOpts));
    }
}
