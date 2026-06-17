package com.chibao.mongodblearning.crud;

import com.mongodb.client.model.Updates;
import org.bson.conversions.Bson;

import java.util.Date;

public class UpdatesBuilderDemo {
    public void buildUpdates() {
        Bson set = Updates.set("name", "Robert");                     // Sets value
        Bson unset = Updates.unset("deprecatedField");                // Deletes field
        Bson inc = Updates.inc("points", 10);                         // Increments numeric value
        Bson mul = Updates.mul("price", 1.15);                        // Multiplies numeric value
        Bson rename = Updates.rename("nickname", "alias");            // Renames field key name
        Bson currDate = Updates.currentDate("lastModified");          // Sets to current datetime

        // Array Modifiers
        Bson push = Updates.push("logins", new Date());               // Appends to array
        Bson addToSet = Updates.addToSet("tags", "java");             // Appends value uniquely
        Bson pull = Updates.pull("tags", "c++");                      // Removes matching value
        Bson popFirst = Updates.popFirst("tags");                     // Removes first element
        Bson popLast = Updates.popLast("tags");                       // Removes last element
    }
}
