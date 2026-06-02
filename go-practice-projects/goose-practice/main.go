package main

import (
	"database/sql"
	"fmt"
	"log"

	"github.com/pressly/goose/v3"
)

type User struct {
	ID       int
	Email    string
	Username string
}

func main() {
	connStr := "host=localhost user=postgres password=postgres dbname=goose_demo sslmode=disable"

	// Connect to database
	db, err := sql.Open("postgres", connStr)
	if err != nil {
		log.Fatal("Failed to connect to database:", err)
	}
	defer db.Close()

	// Test the connection
	if err := db.Ping(); err != nil {
		log.Fatal("Failed to ping database:", err)
	}

	// Run migrations automatically
	log.Println("Running migrations...")
	if err := goose.Up(db, "migrations"); err != nil {
		log.Fatal("Migration failed:", err)
	}
	log.Println("Migrations completed successfully!")

	// Now use the database - Insert users
	log.Println("\nInserting users...")
	users := []struct {
		email    string
		username string
	}{
		{"john@example.com", "john"},
		{"jane@example.com", "jane"},
		{"bob@example.com", "bob"},
	}

	for _, u := range users {
		_, err = db.Exec("INSERT INTO users (email, username) VALUES ($1, $2)",
			u.email, u.username)
		if err != nil {
			log.Printf("Failed to insert user %s: %v", u.username, err)
		} else {
			log.Printf("Inserted user: %s", u.username)
		}
	}

	// Query and display all users
	log.Println("\nQuerying all users...")
	rows, err := db.Query("SELECT id, email, username FROM users")
	if err != nil {
		log.Fatal("Query failed:", err)
	}
	defer rows.Close()

	fmt.Println("\n--- Users in Database ---")
	for rows.Next() {
		var user User
		if err := rows.Scan(&user.ID, &user.Email, &user.Username); err != nil {
			log.Fatal("Scan failed:", err)
		}
		fmt.Printf("ID: %d, Email: %s, Username: %s\n",
			user.ID, user.Email, user.Username)
	}

	if err = rows.Err(); err != nil {
		log.Fatal("Rows error:", err)
	}

	log.Println("\n✓ Application completed successfully!")
}
