# Clean Architecture Example

This project is a demonstration of the Clean Architecture principles applied to a Spring Boot application. It implements a simple money transfer service.

## Features

*   Transfer money between two accounts.
*   Get the balance of an account.

## Technologies

*   Java 21
*   Spring Boot
*   Spring Data JPA
*   H2 Database
*   Lombok
*   Maven
*   JUnit 5
*   Mockito
*   ArchUnit

## Project Structure

The project follows the Clean Architecture principles, separating the code into three main layers:

*   **Domain Layer:** Contains the core business logic and domain models. It is independent of any frameworks or external dependencies.
    *   `application/domain/model`: Contains the domain entities like `Account`, `Activity`, and `Money`.
    *   `application/domain/service`: Contains the domain services that orchestrate the business logic, like `SendMoneyService`.
*   **Application Layer:** Contains the application-specific use cases and defines the ports for interacting with the outside world.
    *   `application/port/in`: Defines the input ports (use cases) like `SendMoneyUseCase`.
    *   `application/port/out`: Defines the output ports for interacting with external systems like databases, e.g., `LoadAccountPort`, `UpdateAccountStatePort`.
*   **Adapter Layer:** Implements the ports defined in the application layer and handles the interaction with external systems.
    *   `adapter/in/web`: Contains the web adapters (controllers) that expose the application's functionality via a REST API.
    *   `adapter/out/persistence`: Contains the persistence adapters that implement the output ports for database access.

## How to Run

1.  Clone the repository.
2.  Build the project using Maven:
    ```bash
    ./mvnw clean install
    ```
3.  Run the application:
    ```bash
    java -jar target/clean-architecture-0.0.1-SNAPSHOT.jar
    ```

## How to Run Tests

To run the tests, execute the following command:

```bash
./mvnw test
```

## API Endpoints

### Send Money

*   **URL:** `/accounts/send/{sourceAccountId}/{targetAccountId}/{amount}`
*   **Method:** `POST`
*   **URL Params:**
    *   `sourceAccountId`: The ID of the source account.
    *   `targetAccountId`: The ID of the target account.
    *   `amount`: The amount of money to transfer.
*   **Example:**
    ```bash
    curl -X POST http://localhost:8080/accounts/send/1/2/100
    ```
