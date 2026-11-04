# Starting point for image-hardening practice; intentionally has no USER.
FROM docker.io/library/busybox:1.37
COPY index.html /www/index.html
EXPOSE 8080
CMD ["httpd", "-f", "-p", "8080", "-h", "/www"]
