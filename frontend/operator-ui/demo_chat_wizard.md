# Chat Wizard Demo Script

## Setup Instructions

1. **Start Backend**
   ```bash
   cd /Users/sam/Documents/GitHub/ai-quality-kit
   source .venv/bin/activate
   export CACHE_ENABLED=false
   export ENABLE_API_LOGGING=false
   export SNOWFLAKE_ACCOUNT=""
   .venv/bin/python -m uvicorn apps.rag_service.main:app --host 0.0.0.0 --port 8000
   ```

2. **Start Frontend**
   ```bash
   cd frontend/operator-ui
   npm run dev
   ```

3. **Open Browser**
   - Navigate to: http://localhost:5173
   - Click the "Chat Wizard" tab

## Demo Flow

### Step 1: Welcome & Target Mode
- **Expected**: Welcome message asking about target mode
- **User Input**: "API endpoint"
- **Expected Response**: Confirmation and request for base URL

### Step 2: Base URL Configuration
- **User Input**: "http://localhost:8000"
- **Expected Response**: URL confirmation and authentication question

### Step 3: Authentication
- **User Input**: "No authentication needed"
- **Expected Response**: Move to provider selection

### Step 4: AI Provider Selection
- **User Input**: "OpenAI"
- **Expected Response**: Provider confirmation and model request

### Step 5: Model Specification
- **User Input**: "gpt-4"
- **Expected Response**: Model confirmation and test suite selection

### Step 6: Test Suite Selection
- **User Input**: "All suites"
- **Expected Response**: Suite confirmation and thresholds question

### Step 7: Thresholds Configuration
- **User Input**: "Use defaults"
- **Expected Response**: Move to volumes configuration

### Step 8: Volumes Configuration
- **User Input**: "Use defaults"
- **Expected Response**: Move to test data configuration

### Step 9: Test Data Configuration
- **User Input**: "Create new data"
- **Expected Response**: Data creation options

### Step 10: Final Configuration
- **User Input**: "Use pre-built datasets"
- **Expected Response**: Configuration summary

### Step 11: Run Tests
- **User Input**: "Run tests"
- **Expected Response**: Test execution confirmation with run ID

## Testing Scenarios

### Scenario 1: Quick Setup
- Use suggestion chips for faster configuration
- Test "All suites" + "Use defaults" path

### Scenario 2: Custom Configuration
- Specify custom thresholds (e.g., "faithfulness_min: 0.9")
- Set custom volumes (e.g., "attack_mutators: 5")

### Scenario 3: MCP Mode
- Choose "MCP server" instead of API
- Test MCP-specific configuration flow

### Scenario 4: Error Handling
- Try invalid URLs
- Test with missing required fields
- Verify graceful error messages

## Expected Behaviors

### UI Elements
- ✅ Tab navigation between Classic Form and Chat Wizard
- ✅ Message bubbles with user/assistant distinction
- ✅ Suggestion chips for common options
- ✅ Progress indicators for completed steps
- ✅ Inline configuration drawer
- ✅ Responsive design on different screen sizes

### State Management
- ✅ Configuration persistence across steps
- ✅ Step completion tracking
- ✅ Validation of required fields
- ✅ Error handling and user feedback

### Integration
- ✅ Backend API calls for test execution
- ✅ Report generation and download
- ✅ Test cancellation support
- ✅ Logging and monitoring

## Debugging Tips

### Console Logs
- Check browser console for React errors
- Verify network requests to backend
- Monitor state changes in Zustand store

### Common Issues
1. **Build Errors**: Run `npm run build` to check for TypeScript errors
2. **Runtime Errors**: Check component imports and dependencies
3. **Styling Issues**: Verify Tailwind CSS classes
4. **State Issues**: Check Zustand store configuration

### Performance
- Monitor component re-renders
- Check for memory leaks in chat history
- Verify efficient state updates

## Success Criteria

- [ ] Chat Wizard tab loads without errors
- [ ] Welcome message displays correctly
- [ ] User can navigate through all configuration steps
- [ ] Configuration is saved and displayed in drawer
- [ ] Tests can be executed successfully
- [ ] Reports are generated and downloadable
- [ ] UI is responsive and accessible
- [ ] Error handling works gracefully
- [ ] State management is stable
- [ ] Integration with backend works correctly

## Next Steps

After successful demo:
1. **User Testing**: Gather feedback from actual users
2. **Performance Optimization**: Monitor and improve response times
3. **Feature Enhancement**: Add voice input, smart defaults
4. **Documentation**: Update user guides and API docs
5. **Testing**: Add unit tests and integration tests
