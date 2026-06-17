package com.chibao.mongodblearning.aggregate;

import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Filters;

public class Demo {
    public static void main(String[] args) {
        Aggregates.match(Filters.eq("status", "ACTIVE"));
    }
}
