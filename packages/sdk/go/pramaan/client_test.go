package pramaan

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
	"time"
)

func TestVerifyUppercasesAndDecodes(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/verify/PRM-ABC" {
			t.Errorf("path = %s", r.URL.Path)
		}
		w.Write([]byte(`{"valid":true}`))
	}))
	defer srv.Close()
	out, err := New(srv.URL, "").Verify(context.Background(), " prm-abc ")
	if err != nil || out["valid"] != true {
		t.Fatalf("got %v %v", out, err)
	}
}

func TestAPIKeyIsSentAndErrorsCarryTheDetail(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-API-Key") != "pk_test_x" {
			t.Errorf("no key")
		}
		w.Header().Set("Retry-After", "7")
		w.Header().Set("Content-Type", "application/problem+json")
		w.WriteHeader(429)
		w.Write([]byte(`{"type":"about:blank","title":"Too Many Requests","status":429,"detail":"slow down"}`))
	}))
	defer srv.Close()
	_, err := New(srv.URL, "pk_test_x").Search(context.Background(), "solar", 3)
	e, ok := err.(*Error)
	if !ok || e.Status != 429 || e.Detail != "slow down" || e.RetryAfter != 7*time.Second {
		t.Fatalf("got %#v", err)
	}
}

func sign(secret string, ts int64, body []byte) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte(fmt.Sprintf("%d.", ts)))
	m.Write(body)
	return hex.EncodeToString(m.Sum(nil))
}

func TestVerifyWebhook(t *testing.T) {
	body := []byte(`{"id":"x"}`)
	now := time.Now().Unix()
	good := "t=" + strconv.FormatInt(now, 10) + ",v1=" + sign("s3cret", now, body)
	if err := VerifyWebhook("s3cret", good, body, 0); err != nil {
		t.Fatal(err)
	}
	if VerifyWebhook("other", good, body, 0) == nil {
		t.Error("wrong secret accepted")
	}
	if VerifyWebhook("s3cret", good, []byte(`{"id":"y"}`), 0) == nil {
		t.Error("changed body accepted")
	}
	old := now - 3600
	if VerifyWebhook("s3cret", "t="+strconv.FormatInt(old, 10)+",v1="+sign("s3cret", old, body), body, 0) == nil {
		t.Error("stale signature accepted")
	}
	if VerifyWebhook("s3cret", "garbage", body, 0) == nil {
		t.Error("malformed header accepted")
	}
}
