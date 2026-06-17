package com.chibao.mongodblearning.crud;

import com.mongodb.client.model.Filters;
import org.bson.conversions.Bson;

public class QueryFiltersDemo {
    public void buildFilters() {
        Bson  eq = Filters.eq("role", "ADMIN");
        Bson ne  = Filters.ne("role", "GUEST");                     // Not Equal
        Bson gt  = Filters.gt("score", 75);                         // Greater Than
        Bson gte = Filters.gte("score", 75);                        // Greater Than or Equal
        Bson lt  = Filters.lt("age", 18);                           // Less Than
        Bson lte = Filters.lte("age", 18);                          // Less Than or Equal
        Bson in  = Filters.in("department", "CS", "EE", "MATH");    // Matches any in list
        Bson nin = Filters.nin("department", "ART", "MUSIC");       // Matches none in list

        // Logical Filters
        Bson andFilter = Filters.and(Filters.eq("status", "ACTIVE"), Filters.gt("age", 21));
        Bson orFilter  = Filters.or(Filters.eq("status", "PENDING"), Filters.lt("balance", 0.0));
        Bson notFilter = Filters.not(Filters.eq("role", "ADMIN"));  // Inverts query logic

        // Element Filters
        Bson existsFilter = Filters.exists("graduationDate", true); // Field existence check

        // Regex Filters (Pattern matching)
        Bson regexFilter = Filters.regex("email", "@university\\.edu$", "i"); // Case-insensitive
    }
}
