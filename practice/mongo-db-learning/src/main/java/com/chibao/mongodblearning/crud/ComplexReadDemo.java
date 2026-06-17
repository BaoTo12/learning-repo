package com.chibao.mongodblearning.crud;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.sun.net.httpserver.Filter;
import org.bson.Document;
import org.bson.conversions.Bson;

import java.util.ArrayList;
import java.util.List;

public class ComplexReadDemo {
    public void run(MongoCollection<Document> collection) {
        Bson nestedFilter = Filters.eq("profile.address.city", "Chicago");
        List<Document> chicagoans = collection.find(nestedFilter).into(new ArrayList<>());

        // 2. Querying Arrays (Primitive values)
        // Matches if "java" is an element in the tags array
        Bson tagFilter = Filters.eq("tags", "java");

        // Exact match: Matches if array is exactly [java, spring] in this order
        Bson exactFilter = Filters.eq("tags", List.of("java", "spring"));

        // Match all elements: Matches if tags contains both "java" and "spring" in any order
        Bson allTagsFilter = Filters.all("tags", List.of("java", "spring"));

        // Array size filter: Matches if array contains exactly 3 items
        Bson sizeFilter = Filters.size("tags", 3);

        Bson subdocArrayFilter1 = Filters.and(Filters.eq("enrollments.courseCode", "Math"), Filters.eq("enrollments.score", 90.0));
        Filters.elemMatch("enrollments", Filters.and(
                Filters.eq("courseCode", "MATH"),
                Filters.gte("score", 90.0)
        ));
    }
}
