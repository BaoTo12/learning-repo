package main

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"
)

// Custom error type for HTTP status codes
type HTTPError struct {
	URL        string
	StatusCode int
	Message    string
}

func (e *HTTPError) Error() string {
	return fmt.Sprintf("HTTP %d for %s: %s", e.StatusCode, e.URL, e.Message)
}

type Result struct {
	URL        string
	StatusCode int
	BodyLength int
	Duration   time.Duration
	Err        error
}

func fetchURL(ctx context.Context, url string, client *http.Client) Result {
	start := time.Now()
	// Nếu timeout xảy ra trong lúc đang request, request sẽ bị hủy
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return Result{URL: url, Err: err, Duration: time.Since(start)}
	}

	// perform the request
	resp, err := client.Do(req)

	if err != nil {
		return Result{URL: url, Err: err, Duration: time.Since(start)}
	}

	defer resp.Body.Close()

	body, err := io.ReadAll(req.Body)
	if err != nil {
		return Result{URL: url, Err: err, Duration: time.Since(start)}
	}

	return Result{
		URL:        url,
		StatusCode: resp.StatusCode,
		BodyLength: len(body),
		Duration:   time.Since(start).Round(time.Millisecond),
	}
}

func fetchURLWithRetry(ctx context.Context, url string, client *http.Client, maxRetries int) Result {
	var lastErr error
	for attempt := 0; attempt < maxRetries; attempt++ {
		select {
		case <-ctx.Done():
			return Result{URL: url, Err: ctx.Err()}
		default:
		}

		result := fetchURL(ctx, url, client)
		if result.Err == nil {
			// Check for rate limiting (429 Too Many Requests)
			if result.StatusCode == http.StatusTooManyRequests {
				// Exponential backoff
				backoff := time.Duration(1<<attempt) * time.Second
				time.Sleep(backoff)
				lastErr = &HTTPError{URL: url, StatusCode: 429, Message: "Rate limited"}
				continue
			}
			return result
		}
		lastErr = result.Err
	}
	return Result{URL: url, Err: fmt.Errorf("failed after %d retries: %w", maxRetries, lastErr)}
}

// Rate-limited worker using a ticker
func rateLimitedWorker(ctx context.Context, jobs <-chan string, results chan<- Result, client *http.Client, wg *sync.WaitGroup, rate time.Duration) {
	defer wg.Done()
	ticker := time.NewTicker(rate)
	defer ticker.Stop()

	for url := range jobs {
		<-ticker.C // Wait for rate limit
		select {
		case <-ctx.Done():
			return
		default:
			results <- fetchURL(ctx, url, client)
		}
	}
}

// sync.WaitGroup dùng để đợi nhiều goroutine chạy xong
// select dùng để chờ và xử lý nhiều channel, select dùng để làm việc với nhiều channel cùng lúc.

func worker(ctx context.Context, id int, jobs <-chan string, results chan<- Result, client *http.Client, wg *sync.WaitGroup) {
	defer wg.Done()
	for url := range jobs {
		select {
		case <-ctx.Done(): // context bị hủy hoặc timeout
			// Context cancelled, stop processing
			results <- Result{URL: url, Err: ctx.Err()}
			return
		default:
			results <- fetchURL(ctx, url, client)
		}
	}
}

func main() {
	urls := []string{
		"https://example.com",
		"https://golang.org",
		"https://github.com",
		// Add hundreds more URLs here
	}
	const (
		numWorkers = 5
		timeout    = 15 * time.Second
	)
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	jobs := make(chan string, len(urls))
	results := make(chan Result, len(urls))

	client := &http.Client{Timeout: 10 * time.Second}

	var wg sync.WaitGroup
	// Start workers

	for i := range numWorkers {
		wg.Add(1)
		go worker(ctx, i, jobs, results, client, &wg)
	}

	// Send jobs
	for _, url := range urls {
		jobs <- url
	}

	close(jobs) // Signal no more jobs

	// Wait for all workers to finish
	wg.Wait()
	close(results) // Signal no more results

	// Collect results
	for r := range results {
		if r.Err != nil {
			fmt.Printf("❌ %s - Error: %v\n", r.URL, r.Err)
		} else {
			fmt.Printf("✅ %s - Status: %d, Size: %d bytes, Time: %v\n",
				r.URL, r.StatusCode, r.BodyLength, r.Duration)
		}
	}
}
