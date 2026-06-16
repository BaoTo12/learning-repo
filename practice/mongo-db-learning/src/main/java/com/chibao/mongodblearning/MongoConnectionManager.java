package com.chibao.mongodblearning;

import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoDatabase;

/**
 * Centrally manages the lifecycle of the MongoDB client and database connections.
 * Ensures a single shared MongoClient instance (singleton pattern) is reused,
 * which is the recommended practice for optimal connection pooling.
 */
public class MongoConnectionManager {

    private static final String DEFAULT_URI = "mongodb://localhost:27017";
    private static final String DEFAULT_DATABASE = "store_db";

    private static MongoClient mongoClient;
    private static MongoDatabase database;

    // Private constructor to prevent instantiation
    private MongoConnectionManager() {}

    /**
     * Retrieves the single, shared MongoClient instance.
     * Initializes it lazily on the first call.
     *
     * @return the active MongoClient instance
     */
    public static synchronized MongoClient getMongoClient() {
        if (mongoClient == null) {
            String uri = System.getenv("MONGODB_URI");
            if (uri == null || uri.isEmpty()) {
                uri = DEFAULT_URI;
            }
            System.out.println("[MongoConnectionManager] Establishing connection to MongoDB at: " + uri);
            mongoClient = MongoClients.create(uri);

            // Register a JVM shutdown hook to close the client and clean up connections when JVM exits
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                synchronized (MongoConnectionManager.class) {
                    if (mongoClient != null) {
                        System.out.println("[MongoConnectionManager] Closing MongoDB client connections...");
                        mongoClient.close();
                        mongoClient = null;
                        database = null;
                    }
                }
            }));
        }
        return mongoClient;
    }

    /**
     * Retrieves the default MongoDatabase instance.
     * Uses the environment variable MONGODB_DATABASE if set, otherwise falls back to 'store_db'.
     *
     * @return the default MongoDatabase instance
     */
    public static synchronized MongoDatabase getDatabase() {
        if (database == null) {
            String dbName = System.getenv("MONGODB_DATABASE");
            if (dbName == null || dbName.isEmpty()) {
                dbName = DEFAULT_DATABASE;
            }
            database = getMongoClient().getDatabase(dbName);
        }
        return database;
    }

    /**
     * Retrieves a MongoDatabase instance with a specific database name.
     *
     * @param dbName the name of the database to retrieve
     * @return the MongoDatabase instance
     */
    public static MongoDatabase getDatabase(String dbName) {
        return getMongoClient().getDatabase(dbName);
    }
}
