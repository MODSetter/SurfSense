FROM node:20-alpine

WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install

# Copy source code
COPY . .

# Build app for production
# For development, we'll mount the source code as a volume
# so the build step will be skipped in development mode

EXPOSE 3000

# Start Next.js in development mode by default
# This will be faster for development since we're mounting the code as a volume
CMD ["pnpm", "dev"] 