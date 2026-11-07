// SPDX-License-Identifier: MIT
package main

import (
	"fmt"
	"log"
	"net/http"
	"time"
)

func page(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	fmt.Fprintln(w, "cks-practice")
}

func main() {
	server := &http.Server{Addr: ":8080", Handler: http.HandlerFunc(page), ReadHeaderTimeout: 5 * time.Second}
	log.Fatal(server.ListenAndServe())
}
