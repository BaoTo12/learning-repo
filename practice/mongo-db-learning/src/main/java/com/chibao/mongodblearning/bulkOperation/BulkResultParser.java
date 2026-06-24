package com.chibao.mongodblearning.bulkOperation;

import com.mongodb.MongoBulkWriteException;
import com.mongodb.bulk.BulkWriteError;
import com.mongodb.bulk.BulkWriteResult;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.WriteModel;
import org.bson.Document;

import java.util.List;

public class BulkResultParser {
    public void executeBulkOperations(MongoCollection<Document> collection, List<WriteModel<Document>> operations) {
        try {
            // Execute the bulk operations
            BulkWriteResult result = collection.bulkWrite(operations);

            System.out.println("Bulk write completed successfully.");
            System.out.println("Inserted: " + result.getInsertedCount());
            System.out.println("Matched: " + result.getMatchedCount());
            System.out.println("Modified: " + result.getModifiedCount());
            System.out.println("Deleted: " + result.getDeletedCount());
            System.out.println("Upserted Count: " + result.getUpserts().size());
        } catch (MongoBulkWriteException e) {
            // Parse partial failure details from exception payload
            System.err.println("Bulk write encountered errors.");

            // e.getWriteResult() retrieves successfully applied updates metrics
            BulkWriteResult result = e.getWriteResult();
            System.err.println("Inserted: " + result.getInsertedCount());
            System.err.println("Modified: " + result.getModifiedCount());

            // Process each individual failure mapped to the failing write models list indexes
            List<BulkWriteError> errors = e.getWriteErrors();
            for (BulkWriteError error : errors) {
                System.err.println("Failure at operation index: " + error.getIndex()
                        + " | Error Code: " + error.getCode()
                        + " | Message: " + error.getMessage());
            }
        }
    }
}
