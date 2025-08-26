# AI Quality Kit - Chat Wizard

## Overview

The Chat Wizard is a new, conversational interface for configuring and running AI quality tests. It provides a ChatGPT-like experience where users can configure test runs through natural language conversation, while maintaining full parity with the classic form interface.

## Features

### 🗣️ Natural Language Configuration
- **Conversational Interface**: Configure tests through chat-like interactions
- **Smart Suggestions**: Clickable suggestion chips for common configurations
- **Step-by-Step Guidance**: Guided configuration through logical steps

### 🔧 Full Configuration Support
- **Target Mode**: API endpoints or MCP servers
- **AI Providers**: OpenAI, Anthropic, Gemini, Custom REST, Mock
- **Test Suites**: All 8 test suites (RAG Quality, Red Team, Safety, etc.)
- **Thresholds**: Customizable quality thresholds
- **Volumes**: Test sample sizes and attack mutators
- **Test Data**: Existing bundles or create new data

### 📱 Modern UI Components
- **Message Bubbles**: Clear user/assistant message distinction
- **Suggestion Chips**: Quick selection of common options
- **Inline Drawer**: Real-time configuration editing
- **Progress Tracking**: Visual step completion indicators

## Usage

### 1. Access the Chat Wizard
- Click the "Chat Wizard" tab in the main interface
- The wizard starts with a welcome message and first question

### 2. Configure Through Conversation
The wizard guides you through these steps:

1. **Target Mode**: Choose between API endpoint or MCP server
2. **Base URL**: Provide the endpoint/server URL
3. **Authentication**: Optional Bearer token or API key
4. **AI Provider**: Select your LLM provider
5. **Model**: Specify the model to test
6. **Test Suites**: Choose which test suites to run
7. **Thresholds**: Set quality thresholds (optional)
8. **Volumes**: Configure test sample sizes (optional)
9. **Test Data**: Use existing bundle or create new

### 3. Run Tests
- Say "run" or "start" when configuration is complete
- Tests execute through the existing orchestrator
- Download JSON/XLSX reports when complete

### 4. Alternative Configuration
- Use the "Show Config" button to see/edit configuration
- Modify settings directly in the inline drawer
- Switch between chat and form modes seamlessly

## Example Conversation

```
Assistant: Hello! I'm your AI Quality Kit assistant. I'll help you configure and run comprehensive tests for your AI system.

Let's start by choosing your target mode. Are you testing an API endpoint or an MCP server?

User: API endpoint

Assistant: Great! You've chosen API mode. Now I need the base URL of your API endpoint. What's the URL? (e.g., http://localhost:8000)

User: http://localhost:8000

Assistant: URL set to: http://localhost:8000

Do you need to provide authentication? If yes, what type? (Bearer token, API key, etc.)

User: No authentication needed

Assistant: No authentication needed. 

Now, which AI provider are you using? (OpenAI, Anthropic, Gemini, Custom REST, or Mock)

User: OpenAI

Assistant: OpenAI selected. Which model would you like to test? (e.g., gpt-4, gpt-3.5-turbo)

User: gpt-4

Assistant: Model set to: gpt-4

Now, which test suites would you like to run? You can choose from:
• RAG Quality (faithfulness, context recall)
• Red Team (adversarial testing)
• Safety (harmful content detection)
• Performance (latency testing)
• Regression (baseline comparison)
• Resilience (failure handling)
• Compliance (PII scanning, RBAC)
• Bias (demographic parity)

Which ones interest you?

User: All suites

Assistant: Great! I've selected these test suites: rag_quality, red_team, safety, performance, regression, resilience, compliance_smoke, bias_smoke

Would you like to customize any thresholds or volumes? You can say "defaults" to use standard settings, or specify custom values.

User: Use defaults

Assistant: Using default thresholds. 

Would you like to customize test volumes? You can say "defaults" or specify custom sample sizes.

User: Use defaults

Assistant: Using default volumes. 

Do you have existing test data, or would you like me to help you create some?

User: Create new data

Assistant: I'll help you create test data. You can:
• Upload files (ZIP, JSON, TXT)
• Provide URLs to data sources
• Paste content directly
• Use our pre-built datasets

What would you prefer?

User: Use pre-built datasets

Assistant: I'll help you create test data in the next step. For now, let me show you a summary of your configuration.

Configuration complete! Here's what we've set up:

**Target Mode:** api
**Base URL:** http://localhost:8000
**Provider:** openai
**Model:** gpt-4
**Test Suites:** rag_quality, red_team, safety, performance, regression, resilience, compliance_smoke, bias_smoke
**Test Data:** Will create new

Ready to run your tests? Just say "run" or "start"!

User: Run tests

Assistant: Tests started successfully! Run ID: run_1234567890_abc123

You can monitor progress and download reports when complete.
```

## Technical Details

### Architecture
- **State Management**: Zustand store for wizard state
- **Component Structure**: Modular React components
- **Type Safety**: Full TypeScript support
- **Styling**: Tailwind CSS with dark mode support

### Integration
- **Backend Compatibility**: Uses existing orchestrator endpoints
- **Form Parity**: Maintains full compatibility with classic form
- **Report Generation**: Same JSON/XLSX output format

### Components
- `ChatWizard`: Main wizard component
- `MessageBubble`: Individual message display
- `SuggestionChips`: Clickable suggestion options
- `ComposerBar`: Chat input interface
- `InlineDrawer`: Configuration editing panel

## Benefits

### For Users
- **Lower Learning Curve**: Natural language instead of form fields
- **Guided Experience**: Step-by-step configuration help
- **Quick Setup**: Suggestion chips for common configurations
- **Flexible Input**: Type naturally or use structured options

### For Developers
- **Maintained Compatibility**: No changes to backend required
- **Modular Design**: Easy to extend and modify
- **Type Safety**: Full TypeScript coverage
- **Responsive UI**: Works on all device sizes

## Future Enhancements

- **Voice Input**: Speech-to-text for hands-free operation
- **Smart Defaults**: AI-powered configuration suggestions
- **Template Library**: Pre-built configuration templates
- **Multi-language Support**: Internationalization
- **Advanced NLP**: Better natural language understanding

## Troubleshooting

### Common Issues
1. **Configuration Not Saving**: Check browser console for errors
2. **Tests Not Running**: Verify backend is running on correct port
3. **UI Not Responsive**: Ensure all dependencies are installed

### Debug Mode
- Open browser developer tools
- Check console for error messages
- Verify network requests to backend

## Support

For issues or questions:
1. Check the browser console for error messages
2. Verify backend connectivity
3. Review configuration settings
4. Check network requests in developer tools
