import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import * as api from '../lib/api'

// Mock the API module
vi.mock('../lib/api', () => ({
  getTestdataMeta: vi.fn(),
  ApiError: class extends Error {
    constructor(public status: number, message: string) {
      super(message)
      this.name = 'ApiError'
    }
  }
}))

// Mock fetch for the run tests functionality
global.fetch = vi.fn()

const mockApi = vi.mocked(api)
const mockFetch = vi.mocked(fetch)

describe('App - Run Tests Form', () => {
  const user = userEvent.setup()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(localStorage.getItem).mockClear()
    vi.mocked(localStorage.setItem).mockClear()
    mockFetch.mockClear()
  })

  describe('TestData ID functionality', () => {
    it('renders testdata_id input field', () => {
      render(<App />)
      
      expect(screen.getByPlaceholderText('Enter testdata_id to override default data sources')).toBeInTheDocument()
      expect(screen.getByText('Use Last')).toBeInTheDocument()
      expect(screen.getByText('Validate')).toBeInTheDocument()
    })

    it('loads last testdata_id from localStorage', async () => {
      vi.mocked(localStorage.getItem).mockReturnValue('stored-123')
      
      render(<App />)
      
      const useLastButton = screen.getByText('Use Last')
      await user.click(useLastButton)
      
      expect(localStorage.getItem).toHaveBeenCalledWith('aqk:last_testdata_id')
      
      const testdataInput = screen.getByPlaceholderText('Enter testdata_id to override default data sources')
      expect(testdataInput).toHaveValue('stored-123')
    })

    it('validates testdata_id successfully', async () => {
      const mockMeta = {
        testdata_id: 'valid-123',
        created_at: '2024-01-01T00:00:00Z',
        expires_at: '2024-01-02T00:00:00Z',
        artifacts: {
          passages: { present: true, count: 10 },
          qaset: { present: true, count: 5 },
          attacks: { present: false },
          schema: { present: false }
        }
      }
      mockApi.getTestdataMeta.mockResolvedValue(mockMeta)
      
      render(<App />)
      
      const testdataInput = screen.getByPlaceholderText('Enter testdata_id to override default data sources')
      await user.type(testdataInput, 'valid-123')
      
      const validateButton = screen.getByText('Validate')
      await user.click(validateButton)
      
      await waitFor(() => {
        expect(screen.getByText('Valid')).toBeInTheDocument()
      })
      
      expect(mockApi.getTestdataMeta).toHaveBeenCalledWith('valid-123', '')
    })

    it('shows invalid status for failed validation', async () => {
      mockApi.getTestdataMeta.mockRejectedValue(new api.ApiError(404, 'Not found'))
      
      render(<App />)
      
      const testdataInput = screen.getByPlaceholderText('Enter testdata_id to override default data sources')
      await user.type(testdataInput, 'invalid-123')
      
      const validateButton = screen.getByText('Validate')
      await user.click(validateButton)
      
      await waitFor(() => {
        expect(screen.getByText('Invalid/Expired')).toBeInTheDocument()
      })
    })

    it('disables run button when testdata_id is invalid', async () => {
      mockApi.getTestdataMeta.mockRejectedValue(new api.ApiError(404, 'Not found'))
      
      render(<App />)
      
      // Set up basic form to enable run button
      const baseUrlInput = screen.getByPlaceholderText('http://localhost:8000')
      await user.clear(baseUrlInput)
      await user.type(baseUrlInput, 'http://localhost:8000')
      
      // Select at least one suite
      const ragQualityCheckbox = screen.getByLabelText('rag_quality')
      await user.click(ragQualityCheckbox)
      
      // Add invalid testdata_id
      const testdataInput = screen.getByPlaceholderText('Enter testdata_id to override default data sources')
      await user.type(testdataInput, 'invalid-123')
      
      const validateButton = screen.getByText('Validate')
      await user.click(validateButton)
      
      await waitFor(() => {
        expect(screen.getByText('Invalid/Expired')).toBeInTheDocument()
      })
      
      const runButton = screen.getByText('Run tests')
      expect(runButton).toBeDisabled()
    })

    it('includes testdata_id in run tests payload', async () => {
      const mockMeta = {
        testdata_id: 'valid-123',
        created_at: '2024-01-01T00:00:00Z',
        expires_at: '2024-01-02T00:00:00Z',
        artifacts: {
          passages: { present: true, count: 10 },
          qaset: { present: true, count: 5 },
          attacks: { present: false },
          schema: { present: false }
        }
      }
      mockApi.getTestdataMeta.mockResolvedValue(mockMeta)
      
      const mockRunResponse = {
        run_id: 'run-123',
        artifacts: { json_path: '/path/to/report.json', xlsx_path: '/path/to/report.xlsx' },
        summary: { total_tests: 10 }
      }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockRunResponse)
      } as Response)
      
      render(<App />)
      
      // Set up form
      const baseUrlInput = screen.getByPlaceholderText('http://localhost:8000')
      await user.clear(baseUrlInput)
      await user.type(baseUrlInput, 'http://localhost:8000')
      
      const ragQualityCheckbox = screen.getByLabelText('rag_quality')
      await user.click(ragQualityCheckbox)
      
      // Add and validate testdata_id
      const testdataInput = screen.getByPlaceholderText('Enter testdata_id to override default data sources')
      await user.type(testdataInput, 'valid-123')
      
      const validateButton = screen.getByText('Validate')
      await user.click(validateButton)
      
      await waitFor(() => {
        expect(screen.getByText('Valid')).toBeInTheDocument()
      })
      
      // Run tests
      const runButton = screen.getByText('Run tests')
      expect(runButton).not.toBeDisabled()
      
      await user.click(runButton)
      
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          'http://localhost:8000/orchestrator/run_tests',
          expect.objectContaining({
            method: 'POST',
            headers: expect.objectContaining({
              'Content-Type': 'application/json'
            }),
            body: expect.stringContaining('"testdata_id":"valid-123"')
          })
        )
      })
    })

    it('does not include testdata_id when empty', async () => {
      const mockRunResponse = {
        run_id: 'run-123',
        artifacts: { json_path: '/path/to/report.json', xlsx_path: '/path/to/report.xlsx' },
        summary: { total_tests: 10 }
      }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockRunResponse)
      } as Response)
      
      render(<App />)
      
      // Set up form without testdata_id
      const baseUrlInput = screen.getByPlaceholderText('http://localhost:8000')
      await user.clear(baseUrlInput)
      await user.type(baseUrlInput, 'http://localhost:8000')
      
      const ragQualityCheckbox = screen.getByLabelText('rag_quality')
      await user.click(ragQualityCheckbox)
      
      // Run tests without testdata_id
      const runButton = screen.getByText('Run tests')
      await user.click(runButton)
      
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          'http://localhost:8000/orchestrator/run_tests',
          expect.objectContaining({
            method: 'POST',
            headers: expect.objectContaining({
              'Content-Type': 'application/json'
            }),
            body: expect.not.stringContaining('"testdata_id"')
          })
        )
      })
    })
  })

  describe('Test Data Panel integration', () => {
    it('renders collapsible test data section', () => {
      render(<App />)
      
      expect(screen.getByText('Test Data')).toBeInTheDocument()
      expect(screen.getByText('Upload, fetch from URLs, or paste custom test data')).toBeInTheDocument()
      
      // Should not show panel content initially (collapsed)
      expect(screen.queryByText('Test Data Intake')).not.toBeInTheDocument()
    })

    it('expands test data panel when clicked', async () => {
      render(<App />)
      
      const testDataButton = screen.getByText('Test Data')
      await user.click(testDataButton)
      
      await waitFor(() => {
        expect(screen.getByText('Test Data Intake')).toBeInTheDocument()
        expect(screen.getByText('Upload Files')).toBeInTheDocument()
      })
    })

    it('collapses test data panel when clicked again', async () => {
      render(<App />)
      
      const testDataButton = screen.getByText('Test Data')
      
      // Expand
      await user.click(testDataButton)
      await waitFor(() => {
        expect(screen.getByText('Test Data Intake')).toBeInTheDocument()
      })
      
      // Collapse
      await user.click(testDataButton)
      await waitFor(() => {
        expect(screen.queryByText('Test Data Intake')).not.toBeInTheDocument()
      })
    })
  })
})
