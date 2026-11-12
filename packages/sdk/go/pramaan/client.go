// Package pramaan is a small Go client for the Pramaan public API: check certificates, search people, read the log, verify webhook signatures.
// Standard library only. Public endpoints need no key. Every method returns the server's JSON decoded into map[string]any so new fields never break callers.
//
//	c := pramaan.New("https://api.example.org", "")        // no key needed for public checks
//	res, err := c.Verify(ctx, "PRM-ABCDEFGHJK")
package pramaan

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// Error is returned when the API answers with an error status. Detail is the server's message (the `detail` field of its problem+json body).
type Error struct {
	Status     int
	Detail     string
	RetryAfter time.Duration // set on 429
}

func (e *Error) Error() string { return fmt.Sprintf("pramaan: %d: %s", e.Status, e.Detail) }

// Client talks to one Pramaan API.
type Client struct {
	BaseURL string
	APIKey  string
	HTTP    *http.Client
}

// New returns a client. apiKey may be empty for the public endpoints.
func New(baseURL, apiKey string) *Client {
	return &Client{BaseURL: strings.TrimRight(baseURL, "/"), APIKey: apiKey, HTTP: &http.Client{Timeout: 30 * time.Second}}
}

func (c *Client) do(ctx context.Context, method, path string, query url.Values, body any) (map[string]any, error) {
	var rdr io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		rdr = bytes.NewReader(b)
	}
	u := c.BaseURL + path
	if len(query) > 0 {
		u += "?" + query.Encode()
	}
	req, err := http.NewRequestWithContext(ctx, method, u, rdr)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if c.APIKey != "" {
		req.Header.Set("X-API-Key", c.APIKey)
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		e := &Error{Status: resp.StatusCode, Detail: strings.TrimSpace(string(raw))}
		var p struct {
			Detail any `json:"detail"`
		}
		if json.Unmarshal(raw, &p) == nil && p.Detail != nil {
			if s, ok := p.Detail.(string); ok {
				e.Detail = s
			} else if b, err := json.Marshal(p.Detail); err == nil {
				e.Detail = string(b)
			}
		}
		if resp.StatusCode == http.StatusTooManyRequests {
			secs, _ := strconv.Atoi(resp.Header.Get("Retry-After"))
			e.RetryAfter = time.Duration(secs) * time.Second
		}
		return nil, e
	}
	if len(raw) == 0 {
		return map[string]any{}, nil
	}
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("pramaan: unreadable response: %w", err)
	}
	return out, nil
}

func code(c string) string { return strings.ToUpper(strings.TrimSpace(c)) }

// Verify asks whether a certificate is genuine, unchanged and not revoked.
func (c *Client) Verify(ctx context.Context, certCode string) (map[string]any, error) {
	return c.do(ctx, "GET", "/v1/verify/"+url.PathEscape(code(certCode)), nil, nil)
}

// VerifyBatch checks up to 50 certificates in one call.
func (c *Client) VerifyBatch(ctx context.Context, codes []string) (map[string]any, error) {
	up := make([]string, len(codes))
	for i, x := range codes {
		up[i] = code(x)
	}
	return c.do(ctx, "POST", "/v1/verify/batch", nil, map[string]any{"codes": up})
}

// Certificate returns the certificate (payload, digest, signature, key id).
func (c *Client) Certificate(ctx context.Context, certCode string) (map[string]any, error) {
	return c.do(ctx, "GET", "/v1/certificates/"+url.PathEscape(code(certCode)), nil, nil)
}

// Credential returns the certificate as a W3C Verifiable Credential 2.0.
func (c *Client) Credential(ctx context.Context, certCode string) (map[string]any, error) {
	return c.do(ctx, "GET", "/v1/certificates/"+url.PathEscape(code(certCode))+"/vc", nil, nil)
}

// Search finds people in plain language; every hit says why it matched.
func (c *Client) Search(ctx context.Context, query string, limit int) (map[string]any, error) {
	return c.do(ctx, "POST", "/v1/search", nil, map[string]any{"query": query, "limit": limit})
}

// Profile returns one approved, consenting person by slug.
func (c *Client) Profile(ctx context.Context, slug string) (map[string]any, error) {
	return c.do(ctx, "GET", "/v1/profiles/"+url.PathEscape(slug), nil, nil)
}

// LogCheckpoint returns the signed Merkle root and size of the public log.
func (c *Client) LogCheckpoint(ctx context.Context) (map[string]any, error) {
	return c.do(ctx, "GET", "/v1/transparency/checkpoint", nil, nil)
}

// PublicKeys returns the Ed25519 keys certificates are signed with.
func (c *Client) PublicKeys(ctx context.Context) (map[string]any, error) {
	return c.do(ctx, "GET", "/.well-known/pramaan-keys.json", nil, nil)
}

// VerifyWebhook checks the X-Pramaan-Signature header ("t=<unix>,v1=<hex hmac-sha256 of "<t>.<body>">") of a delivery.
// tolerance is how old a signature may be (the default of 5 minutes is used when it is zero).
func VerifyWebhook(secret, header string, body []byte, tolerance time.Duration) error {
	if tolerance == 0 {
		tolerance = 5 * time.Minute
	}
	var ts, sig string
	for _, part := range strings.Split(header, ",") {
		kv := strings.SplitN(strings.TrimSpace(part), "=", 2)
		if len(kv) != 2 {
			continue
		}
		switch kv[0] {
		case "t":
			ts = kv[1]
		case "v1":
			sig = kv[1]
		}
	}
	secs, err := strconv.ParseInt(ts, 10, 64)
	if err != nil || sig == "" {
		return errors.New("pramaan: malformed signature header")
	}
	if d := time.Since(time.Unix(secs, 0)); d > tolerance || d < -tolerance {
		return errors.New("pramaan: signature timestamp is outside the allowed window")
	}
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(ts + "."))
	mac.Write(body)
	want := hex.EncodeToString(mac.Sum(nil))
	if !hmac.Equal([]byte(want), []byte(sig)) {
		return errors.New("pramaan: signature does not match")
	}
	return nil
}
