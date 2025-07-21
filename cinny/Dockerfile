# Builder
FROM node:20.12.2-alpine3.18 as builder

# Install git
RUN apk add --no-cache git

# Set working directory
WORKDIR /src

# Clone the specific repository and branch
RUN git clone --depth 1 --branch dev https://github.com/GigiaJ/cinny.git .

# Copy our custom config to overwrite the repository's config before building
COPY config.json /src/config.json

# Install dependencies
RUN npm ci

# Set Node options for build (important for memory allocation)
ENV NODE_OPTIONS=--max_old_space_size=4096

# Build the application (this will include our custom config.json)
RUN npm run build

# App
FROM nginx:1.27.4-alpine

# Copy built files and nginx config from the repository
COPY --from=builder /src/dist /app
COPY --from=builder /src/docker-nginx.conf /etc/nginx/conf.d/default.conf

# Remove default nginx html and create symlink
RUN rm -rf /usr/share/nginx/html \
  && ln -s /app /usr/share/nginx/html
