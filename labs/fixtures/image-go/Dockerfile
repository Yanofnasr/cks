# SPDX-License-Identifier: MIT
# Deliberately single-stage starting point for SC01.
FROM docker.io/library/golang:1.26-alpine
WORKDIR /src
COPY main.go .
RUN CGO_ENABLED=0 go build -trimpath -o /server main.go
EXPOSE 8080
CMD ["/server"]
