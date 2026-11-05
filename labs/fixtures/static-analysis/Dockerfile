# SPDX-License-Identifier: MIT
# SC08 scanner input only. Deliberately flawed: DO NOT BUILD OR RUN unchanged.
FROM docker.io/library/busybox:latest
COPY . /www
EXPOSE 8080
CMD ["httpd", "-f", "-p", "8080", "-h", "/www"]
