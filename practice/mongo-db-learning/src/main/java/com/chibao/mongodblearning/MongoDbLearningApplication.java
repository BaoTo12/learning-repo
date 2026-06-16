package com.chibao.mongodblearning;


import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

import java.util.List;

public class MongoDbLearningApplication {

    public static void main(String[] args) {
        // Retrieve the database connection from the centralized connection manager
        MongoDatabase database = MongoConnectionManager.getDatabase("store_db");

        MongoCollection<Document> collection = database.getCollection("students");

            // clear data on collection
            collection.drop();
            System.out.println("Sandbox collection dropped for a clean run.");

            // create student document;
            Document student = new Document("_id", "STD-101")
                    .append("fullName", "Chi Bao")
                    .append("gpa", 3.8)
                    .append("enrolled", true)
                    .append("courses", List.of("CS-529", "CS-509"));

            collection.insertOne(student);
            System.out.println("Created: Inserted Student document STD-101.");

            // get student
            Document retrievedStudent = collection.find(Filters.eq("_id", "STD-101")).first();
            System.out.println(retrievedStudent);
            if (retrievedStudent != null) {
                System.out.println("Read: Retrieved Student document: " + retrievedStudent.toJson());

                // Extracting java primitives from Document safely
                String name = retrievedStudent.getString("fullName");
                double gpa = retrievedStudent.getDouble("gpa");
                System.out.println("Parsed Primitive Data -> Name: " + name + ", GPA: " + gpa);
            }

            // 7. UPDATE: Add a course to the array and update the GPA
            // combine() merges multiple update operators into one atomic write
            collection.findOneAndUpdate(
                    Filters.eq("_id", "STD-101"),
                    Updates.combine(
                            Updates.push("courses", "CS-512"),
                            Updates.set("gpa", 4.0)
                    )
            );
            retrievedStudent = collection.find(Filters.eq("_id", "STD-01")).first();
            System.out.println(retrievedStudent);

            // Verify the update
            Document updatedStudent = collection.find(Filters.eq("_id", "STD-101")).first();
            if (updatedStudent != null) {
                System.out.println("Verification Read: " + updatedStudent.toJson());
            }

            // 8. DELETE: Remove the student document from the collection
            collection.deleteOne(Filters.eq("_id", "STD-101"));
            System.out.println("Deleted: Removed Student document.");

            // Confirm removal
            long countAfterDelete = collection.countDocuments(Filters.eq("_id", "STD-101"));
            System.out.println("Count remaining for STD-101: " + countAfterDelete);
    }
}
