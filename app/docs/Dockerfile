FROM python:3.9-slim as builder

# Install dependencies
RUN pip install mkdocs mkdocs-material

# Set up the working directory
WORKDIR /app

# Copy the documentation source files
COPY app/docs-src ./docs
COPY app/docs/mkdocs.yml .

# Build the documentation
RUN mkdocs build

# Final stage
FROM nginx:1.21-alpine

# Copy the built documentation
COPY --from=builder /app/site /usr/share/nginx/html

# Configure Nginx
COPY app/docs/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Run Nginx
CMD ["nginx", "-g", "daemon off;"] 