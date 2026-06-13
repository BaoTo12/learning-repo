package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/BaoTo12/go-calculator/calculator"
)

func main() {
	fmt.Println("=== Go CLI Calculator ===")
	fmt.Println("Enter expressions like: 5 + 3")
	fmt.Println("Supported operations: +, -, *, /")
	fmt.Println("Type 'quit' or 'exit' to end")
	fmt.Println()

	scanner := bufio.NewScanner(os.Stdin)

	for {
		fmt.Print("> ")
		if !scanner.Scan() {
			break
		}

		input := strings.TrimSpace(scanner.Text())
		if input == "" {
			continue
		}

		lowerInput := strings.ToLower(input)
		if lowerInput == "quit" || lowerInput == "exit" {
			fmt.Println("Goodbye!")
			break
		}

		result, err := processExpression(input)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			continue
		}

		fmt.Printf("Result: %v\n", result)
	}

	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "Error reading input: %v\n", err)
	}
}

func processExpression(input string) (float64, error) {
	// Split input into parts: number, operator, number
	parts := strings.Fields(input)
	if len(parts) != 3 {
		return 0, fmt.Errorf("invalid format: expected 'number operator number', got %d parts", len(parts))
	}

	// Parse first number
	a, err := strconv.ParseFloat(parts[0], 64)
	if err != nil {
		return 0, fmt.Errorf("invalid first number '%s': %v", parts[0], err)
	}

	// Parse operator
	var op calculator.Operation
	switch parts[1] {
	case "+":
		op = calculator.Add
	case "-":
		op = calculator.Subtract
	case "*":
		op = calculator.Multiply
	case "/":
		op = calculator.Divide
	default:
		return 0, fmt.Errorf("unsupported operator '%s': use +, -, *, or /", parts[1])
	}

	// Parse second number
	b, err := strconv.ParseFloat(parts[2], 64)
	if err != nil {
		return 0, fmt.Errorf("invalid second number '%s': %v", parts[2], err)
	}

	return calculator.Calculate(a, b, op)
}
