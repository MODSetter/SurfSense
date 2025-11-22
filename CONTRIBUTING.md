# Contributing to SurfSense

Hey! 👋 Thanks for checking out **SurfSense**. We're stoked that you're interested in helping improve the project. Whether it's fixing bugs, suggesting features, improving docs, or just joining the conversation — every bit helps.

## 🧠 Before You Start

**Join Our Discord**  
Want to stay in the loop, ask questions, or get feedback before starting something?  
Hop into the official SurfSense community:  
👉 [https://discord.gg/ejRNvftDp9](https://discord.gg/ejRNvftDp9)

That's where the *latest updates*, *internal discussions*, and *collaborations* happen.

## 📌 What Can You Work On?

There are 3 main ways to contribute:

### ✅ 1. Pick From the Roadmap
We maintain a public roadmap with well-scoped issues and features you can work on:  
🔗 [SurfSense GitHub Project Roadmap](https://github.com/users/MODSetter/projects/2)

> 💡 **Tip**: Look for tasks in `Backlog` or `Ready` status.

### 💡 2. Propose Something New
Have an idea that's not on the roadmap?

1. First, check for an existing issue
2. If it doesn't exist, create a new issue explaining your feature or enhancement
3. Wait for feedback from maintainers
4. Once approved, you're welcome to start working on a PR!

### 🐞 3. Report Bugs or Fix Them
Found a bug? Create an issue with:

- **Steps to reproduce** the issue
- **Expected vs actual behavior**
- **Environment details** (OS, browser, version)
- **Any relevant logs or screenshots**

Want to fix it? Go for it! Just link the issue in your PR.

## 🛠️ Development Setup

### Prerequisites
- **Docker & Docker Compose** (recommended) OR manual setup
- **Node.js** (v18+ for web frontend)
- **Python** (v3.11+ for backend)
- **PostgreSQL** with **PGVector** extension
- **API Keys** for external services you're testing

### Quick Start
1. **Clone the repository**
   ```bash
   git clone https://github.com/MODSetter/SurfSense.git
   cd SurfSense
   ```

2. **Choose your setup method**:
   - **Docker Setup**: Follow the [Docker Setup Guide](./DOCKER_SETUP.md)
   - **Manual Setup**: Follow the [Installation Guide](https://www.surfsense.net/docs/)

3. **Configure services**:
   - Set up PGVector & PostgreSQL
   - Configure a file ETL service: `Unstructured.io` or `LlamaIndex`
   - Add API keys for external services

For detailed setup instructions, refer to our [Installation Guide](https://www.surfsense.net/docs/).

## 🏗️ Project Structure

SurfSense consists of three main components:

- **`surfsense_backend/`** - Python/FastAPI backend service
- **`surfsense_web/`** - Next.js web application
- **`surfsense_browser_extension/`** - Browser extension for data collection

## 🧪 Development Guidelines

### Code Quality & Pre-commit Hooks
We use pre-commit hooks to maintain code quality, security, and consistency across the codebase. Before you start developing:

1. **Install and set up pre-commit hooks** - See our detailed [Pre-commit Guide](./PRE_COMMIT.md)
2. **Understand the automated checks** that will run on your code
3. **Learn about bypassing hooks** when necessary (use sparingly!)

### Code Style
- **Backend**: Follow Python PEP 8 style guidelines
- **Frontend**: Use TypeScript and follow the existing code patterns
- **Formatting**: Use the project's configured formatters (Black for Python, Prettier for TypeScript)

### Commit Messages
Use clear, descriptive commit messages:
```
feat: add document search functionality
fix: resolve pagination issue in chat history
docs: update installation guide
refactor: improve error handling in connectors
```

### Testing
- Write tests for new features and bug fixes
- Ensure existing tests pass before submitting
- Include integration tests for API endpoints

### Branch Naming
Use descriptive branch names:
- `feature/add-document-search`
- `fix/pagination-issue`
- `docs/update-contributing-guide`

## 🔄 Pull Request Process

### Before Submitting
1. **Create an issue** first (unless it's a minor fix)
2. **Fork the repository** and create a feature branch
3. **Make your changes** following the coding guidelines
4. **Test your changes** thoroughly
5. **Update documentation** if needed

### PR Requirements
- **One feature or fix per PR** - keep changes focused
- **Link related issues** in the PR description
- **Include screenshots or demos** for UI changes
- **Write descriptive PR title and description**
- **Ensure CI passes** before requesting review


## 🔍 Code Review Process

1. **Automated checks** must pass (CI/CD pipeline)
2. **At least one maintainer** will review your PR
3. **Address feedback** promptly and professionally
4. **Squash commits** if requested to keep history clean
5. **Celebrate** when your PR gets merged! 🎉

## 📚 Documentation Maintenance

Documentation is critical for project maintainability. Every PR should include appropriate documentation updates.

### Required Documentation Updates

When contributing code, update the following documentation as applicable:

#### 1. **README.md**
Update if your PR includes:
- New features or capabilities
- Changes to setup/installation steps
- New dependencies or prerequisites
- Changes to project structure

#### 2. **SECURITY.md**
Update if your PR involves:
- Authentication or authorization changes
- Permission model modifications
- Audit logging additions
- Security-critical code changes
- Vulnerability fixes

#### 3. **API Documentation**
Update if your PR changes:
- API endpoints (new, modified, or deprecated)
- Request/response schemas
- Query parameters or request bodies
- Error codes or responses
- Authentication requirements

Include:
- Clear endpoint descriptions
- Request/response examples
- Error scenarios
- Rate limiting details

#### 4. **Code Comments**
Add or update comments for:
- Complex algorithms or logic
- Security-critical sections
- Non-obvious implementation decisions
- Performance optimizations
- Workarounds or temporary solutions

**Best Practices:**
- Use docstrings for all public functions/classes
- Explain the "why", not just the "what"
- Keep comments up-to-date with code changes

#### 5. **Architecture Documentation**
Document significant changes:
- New components or services
- Database schema changes
- Integration patterns
- Caching strategies
- Security models

Create or update diagrams where helpful.

#### 6. **Configuration Documentation**
Update if adding:
- Environment variables
- Configuration file options
- Feature flags
- Service integrations

Include:
- Description of each setting
- Valid values and defaults
- Examples
- Security considerations

#### 7. **Migration Guides**
Create migration guides for:
- Breaking changes
- Database migrations
- Configuration changes requiring user action
- Deprecated features

Include:
- Step-by-step migration instructions
- Before/after examples
- Troubleshooting tips

#### 8. **CHANGELOG**
Add entries for:
- User-facing changes
- New features
- Bug fixes
- Breaking changes
- Deprecations

Follow [Keep a Changelog](https://keepachangelog.com/) format:
```markdown
## [Unreleased]
### Added
- Community prompts feature with 31 curated prompts

### Fixed
- Image compression error handling now returns 400 for invalid files

### Changed
- Improved cache performance for community prompts endpoint
```

### Documentation Quality Standards

#### Clarity
- Write for developers unfamiliar with the code
- Use simple, concise language
- Define technical terms
- Avoid jargon without explanation

#### Completeness
- Include all necessary information
- Provide code examples for APIs
- Document edge cases and limitations
- List dependencies and prerequisites

#### Accuracy
- Keep docs synchronized with code
- Test examples before committing
- Update docs in the same PR as code changes
- Review docs as carefully as code

#### Accessibility
- Use proper Markdown formatting
- Include table of contents for long docs
- Add screenshots for UI changes
- Provide both high-level and detailed views

### Documentation Review Checklist

Before submitting your PR, verify:
- [ ] All affected documentation files updated
- [ ] Code examples tested and working
- [ ] Links to related docs/issues included
- [ ] Screenshots updated (if UI changed)
- [ ] No broken links or formatting issues
- [ ] Technical terms explained or linked
- [ ] Spelling and grammar checked

### Where to Find Documentation
- **Main docs**: `/docs/` directory
- **API docs**: `/surfsense_backend/app/routes/` (inline docstrings)
- **Component docs**: Co-located with code in relevant directories
- **User docs**: https://www.surfsense.net/docs/

### Getting Documentation Help
If unsure about documentation requirements:
1. Check similar PRs for reference
2. Ask in the PR discussion
3. Request review from maintainers
4. Join Discord for real-time help

## 🆘 Getting Help

Stuck? Need clarification? Here's how to get help:

1. **Check existing issues** - your question might already be answered
2. **Search the docs** - [https://www.surfsense.net/docs/](https://www.surfsense.net/docs/)
3. **Ask in Discord** - [https://discord.gg/ejRNvftDp9](https://discord.gg/ejRNvftDp9)
4. **Create an issue** - if it's a bug or feature request

## ⭐ Other Ways to Contribute

Not ready to code? You can still help!

- **Give us a star** ⭐ on GitHub
- **Share SurfSense** with your community
- **Provide feedback** on Discord
- **Help triage issues** and validate bug reports
- **Improve documentation** and examples
- **Write tutorials** or blog posts about SurfSense

## 🎯 Recognition

We appreciate all contributions! Contributors will be:
- **Acknowledged** in release notes
- **Listed** in our contributors section
- **Invited** to join our contributors' Discord channel
- **Eligible** for special contributor badges

## 📄 License

By contributing to SurfSense, you agree that your contributions will be licensed under the same license as the project.

---

**Thank you for contributing to SurfSense!** 🚀  
Together, we're building something awesome.





