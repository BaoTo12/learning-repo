package com.chibao.mongodblearning;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.UpdateOptions;
import com.mongodb.client.model.Updates;
import org.bson.Document;
import org.bson.conversions.Bson;

import java.util.List;

public class CRUDOperations {
    public void updateScoreInArray(MongoCollection<Document> collection, String studentId, String courseId, int newScore) {

        var filter = Filters.eq("_id", studentId);

        var update = Updates.set("courses.$[c].score", newScore);

        List<Document> arrayFilters = List.of(new Document("c.courseId", courseId));

        UpdateOptions options = new UpdateOptions().arrayFilters(arrayFilters);
        collection.updateOne(filter, update, options);
    }
    public void updateProductPriceAndStock(MongoCollection<Document> collection, String productId, double newPrice, int stockIncrement) {

        var filter = Filters.eq("_id", productId);

        Bson update = Updates.combine(
                Updates.set("price", newPrice),
                Updates.inc("stock", stockIncrement)
        );

        collection.updateOne(filter, update);
    }
    public void deleteProduct(MongoCollection<Document> collection, String productId) {
        collection.deleteOne(Filters.eq("_id", productId));
    }
}
