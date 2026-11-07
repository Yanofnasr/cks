// SPDX-License-Identifier: MIT
package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestPracticePage(t *testing.T) {
	response := httptest.NewRecorder()
	page(response, httptest.NewRequest(http.MethodGet, "/", nil))
	if response.Code != http.StatusOK || response.Body.String() != "cks-practice\n" {
		t.Fatalf("unexpected response: %d %q", response.Code, response.Body.String())
	}
	if got := response.Header().Get("Content-Type"); got != "text/plain; charset=utf-8" {
		t.Fatalf("unexpected content type: %q", got)
	}
}
