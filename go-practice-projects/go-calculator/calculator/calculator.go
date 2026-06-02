package calculator

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
)

type Operation int

const (
	Add Operation = iota
	Subtract
	Multiply
	Divide
)

func (op Operation) String() string {
	switch op {
	case Add:
		return "+"
	case Subtract:
		return "-"
	case Multiply:
		return "*"
	case Divide:
		return "/"
	default:
		return "Unknown"
	}
}

// Calculate performs the specified operation on two numbers

func Calculate(a, b float64, op Operation) (float64, error) {
	switch op {
	case Add:
		return a + b, nil
	case Subtract:
		return a - b, nil
	case Multiply:
		return a * b, nil
	case Divide:
		if b == 0 {
			return 0, fmt.Errorf("Division by zero is not allow")
		}
		return a / b, nil
	default:
		return 0, fmt.Errorf("Unsupported Operations: %v", op)
	}
}

func Evaluate(expr string) (float64, error) {
	// Tokenize the expression
	tokens := tokenize(expr)
	if len(tokens) == 0 {
		return 0, errors.New("empty expression")
	}

	// Simple left-to-right evaluation (no operator precedence)
	result, err := strconv.ParseFloat(tokens[0], 64)
	if err != nil {
		return 0, fmt.Errorf("invalid number '%s': %v", tokens[0], err)
	}

	for i := 1; i < len(tokens); i += 2 {
		if i+1 >= len(tokens) {
			return 0, errors.New("incomplete expression")
		}

		op := tokens[i]
		b, err := strconv.ParseFloat(tokens[i+1], 64)
		if err != nil {
			return 0, fmt.Errorf("invalid number '%s': %v", tokens[i+1], err)
		}

		switch op {
		case "+":
			result += b
		case "-":
			result -= b
		case "*":
			result *= b
		case "/":
			if b == 0 {
				return 0, errors.New("division by zero")
			}
			result /= b
		default:
			return 0, fmt.Errorf("unsupported operator '%s'", op)
		}
	}

	return result, nil
}

// tokenize splits an expression into tokens (numbers and operators)
func tokenize(expr string) []string {
	var tokens []string
	current := ""
	for _, ch := range expr {
		if ch == '+' || ch == '-' || ch == '*' || ch == '/' {
			if current != "" {
				tokens = append(tokens, strings.TrimSpace(current))
				current = ""
			}
			tokens = append(tokens, string(ch))
		} else {
			current += string(ch)
		}
	}
	if current != "" {
		tokens = append(tokens, strings.TrimSpace(current))
	}
	return tokens
}
