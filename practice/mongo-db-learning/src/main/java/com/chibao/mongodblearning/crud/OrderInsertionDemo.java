package com.chibao.mongodblearning.crud;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.InsertManyOptions;

import javax.swing.text.Document;
import java.util.List;

public class OrderInsertionDemo {
    public void run (MongoCollection<Document> collection, List<Document>documents){
        collection.insertMany(documents, new InsertManyOptions().ordered(true));
        collection.insertMany(documents, new InsertManyOptions().ordered(false));
    }
}
