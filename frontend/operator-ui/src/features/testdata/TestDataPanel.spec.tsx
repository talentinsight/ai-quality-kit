import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TestDataPanel from './TestDataPanel'
import * as api from '../../lib/api'

// Mock the API module
vi.mock('../../lib/api', () => ({
  postTestdataUpload: vi.fn(),
  postTestdataByUrl: vi.fn(),
  postTestdataPaste: vi.fn(),
  getTestdataMeta: vi.fn(),
  ApiError: class extends Error {
    constructor(public status: number, message: string) {
      super(message)
      this.name = 'ApiError'
    }
  }
}))

const mockApi = vi.mocked(api)

describe('TestDataPanel', () => {
  const user = userEvent.setup()
  const mockToken = 'test-token'

  beforeEach(() => {
    vi.clearAllMocks()
    // Reset localStorage mock
    vi.mocked(localStorage.setItem).mockClear()
    vi.mocked(localStorage.getItem).mockClear()
  })

  describe('Upload Tab', () => {
    it('renders upload tab by default', () => {
      render(<TestDataPanel token={mockToken} />)
      
      expect(screen.getByText('Test Data Intake')).toBeInTheDocument()
      expect(screen.getByText('Upload Files')).toBeInTheDocument()
      expect(screen.getByLabelText('Passages')).toBeInTheDocument()
      expect(screen.getByLabelText('QA Set')).toBeInTheDocument()
      expect(screen.getByLabelText('Attacks')).toBeInTheDocument()
      expect(screen.getByLabelText('Schema')).toBeInTheDocument()
    })

    it('shows error when no files selected', async () => {
      render(<TestDataPanel token={mockToken} />)
      
      const uploadButton = screen.getByText('Upload Files')
      await user.click(uploadButton)
      
      await waitFor(() => {
        expect(screen.getByText('No files selected')).toBeInTheDocument()
      })
    })

    it('uploads files and shows success result', async () => {
      const mockResponse = {
        testdata_id: 'test-123',
        artifacts: ['passages', 'qaset'],
        counts: { passages: 10, qaset: 5 }
      }
      mockApi.postTestdataUpload.mockResolvedValue(mockResponse)

      render(<TestDataPanel token={mockToken} />)
      
      // Create mock files
      const passagesFile = new File(['{"id":"1","text":"test"}'], 'passages.jsonl', { type: 'application/jsonl' })
      const qasetFile = new File(['{"qid":"1","question":"test","expected_answer":"test"}'], 'qaset.jsonl', { type: 'application/jsonl' })
      
      // Upload files
      const passagesInput = screen.getByLabelText('Passages')
      const qasetInput = screen.getByLabelText('QA Set')
      await user.upload(passagesInput, passagesFile)
      await user.upload(qasetInput, qasetFile)
      
      const uploadButton = screen.getByText('Upload Files')
      await user.click(uploadButton)
      
      await waitFor(() => {
        expect(screen.getByText('Upload successful')).toBeInTheDocument()
        expect(screen.getByText('test-123')).toBeInTheDocument()
        expect(screen.getByText('passages (10 items)')).toBeInTheDocument()
        expect(screen.getByText('qaset (5 items)')).toBeInTheDocument()
      })
      
      expect(localStorage.setItem).toHaveBeenCalledWith('aqk:last_testdata_id', 'test-123')
    })

    it('shows authentication error for 401 response', async () => {
      mockApi.postTestdataUpload.mockRejectedValue(new api.ApiError(401, 'Unauthorized'))

      render(<TestDataPanel token={mockToken} />)
      
      const passagesFile = new File(['{"id":"1","text":"test"}'], 'passages.jsonl', { type: 'application/jsonl' })
      const passagesInput = screen.getByLabelText('Passages')
      await user.upload(passagesInput, passagesFile)
      
      const uploadButton = screen.getByText('Upload Files')
      await user.click(uploadButton)
      
      await waitFor(() => {
        expect(screen.getByText('Authentication required')).toBeInTheDocument()
      })
    })
  })

  describe('URL Tab', () => {
    it('switches to URL tab and shows URL inputs', async () => {
      render(<TestDataPanel token={mockToken} />)
      
      const urlTab = screen.getByText('URL')
      await user.click(urlTab)
      
      expect(screen.getByLabelText('Passages URL')).toBeInTheDocument()
      expect(screen.getByLabelText('QA Set URL')).toBeInTheDocument()
      expect(screen.getByLabelText('Attacks URL')).toBeInTheDocument()
      expect(screen.getByLabelText('Schema URL')).toBeInTheDocument()
      expect(screen.getByText('Ingest from URLs')).toBeInTheDocument()
    })

    it('shows error when no URLs provided', async () => {
      render(<TestDataPanel token={mockToken} />)
      
      const urlTab = screen.getByText('URL')
      await user.click(urlTab)
      
      const ingestButton = screen.getByText('Ingest from URLs')
      await user.click(ingestButton)
      
      await waitFor(() => {
        expect(screen.getByText('No URLs provided')).toBeInTheDocument()
      })
    })

    it('ingests from URLs successfully', async () => {
      const mockResponse = {
        testdata_id: 'url-123',
        artifacts: ['passages'],
        counts: { passages: 15 }
      }
      mockApi.postTestdataByUrl.mockResolvedValue(mockResponse)

      render(<TestDataPanel token={mockToken} />)
      
      const urlTab = screen.getByText('URL')
      await user.click(urlTab)
      
      const passagesUrlInput = screen.getByLabelText('Passages URL')
      await user.type(passagesUrlInput, 'https://example.com/passages.jsonl')
      
      const ingestButton = screen.getByText('Ingest from URLs')
      await user.click(ingestButton)
      
      await waitFor(() => {
        expect(screen.getByText('URL ingestion successful')).toBeInTheDocument()
        expect(screen.getByText('url-123')).toBeInTheDocument()
      })
      
      expect(mockApi.postTestdataByUrl).toHaveBeenCalledWith(
        { urls: { passages: 'https://example.com/passages.jsonl' } },
        mockToken
      )
    })
  })

  describe('Paste Tab', () => {
    it('switches to paste tab and shows text areas', async () => {
      render(<TestDataPanel token={mockToken} />)
      
      const pasteTab = screen.getByText('Paste')
      await user.click(pasteTab)
      
      expect(screen.getByLabelText('Passages (JSONL)')).toBeInTheDocument()
      expect(screen.getByLabelText('QA Set (JSONL)')).toBeInTheDocument()
      expect(screen.getByLabelText('Attacks (Text/YAML)')).toBeInTheDocument()
      expect(screen.getByLabelText('Schema (JSON)')).toBeInTheDocument()
      expect(screen.getByText('Process Content')).toBeInTheDocument()
    })

    it('processes pasted content successfully', async () => {
      const mockResponse = {
        testdata_id: 'paste-123',
        artifacts: ['qaset'],
        counts: { qaset: 3 }
      }
      mockApi.postTestdataPaste.mockResolvedValue(mockResponse)

      render(<TestDataPanel token={mockToken} />)
      
      const pasteTab = screen.getByText('Paste')
      await user.click(pasteTab)
      
      const qasetTextarea = screen.getByLabelText('QA Set (JSONL)')
      await user.click(qasetTextarea)
      await user.clear(qasetTextarea)
      await user.paste('{"qid":"1","question":"What?","expected_answer":"Answer"}')
      
      const processButton = screen.getByText('Process Content')
      await user.click(processButton)
      
      await waitFor(() => {
        expect(screen.getByText('Paste ingestion successful')).toBeInTheDocument()
        expect(screen.getByText('paste-123')).toBeInTheDocument()
      })
      
      expect(mockApi.postTestdataPaste).toHaveBeenCalledWith(
        { qaset: '{"qid":"1","question":"What?","expected_answer":"Answer"}' },
        mockToken
      )
    })
  })

  describe('Validation', () => {
    it('validates testdata_id successfully', async () => {
      const mockResponse = {
        testdata_id: 'test-123',
        artifacts: ['passages', 'qaset'],
        counts: { passages: 10, qaset: 5 }
      }
      mockApi.postTestdataUpload.mockResolvedValue(mockResponse)
      
      const mockMeta = {
        testdata_id: 'test-123',
        created_at: '2024-01-01T00:00:00Z',
        expires_at: '2024-01-02T00:00:00Z',
        artifacts: {
          passages: { present: true, count: 10, sha256: 'abc123' },
          qaset: { present: true, count: 5, sha256: 'def456' },
          attacks: { present: false },
          schema: { present: false }
        }
      }
      mockApi.getTestdataMeta.mockResolvedValue(mockMeta)

      render(<TestDataPanel token={mockToken} />)
      
      // First upload some data
      const passagesFile = new File(['{"id":"1","text":"test"}'], 'passages.jsonl', { type: 'application/jsonl' })
      const passagesInput = screen.getByLabelText('Passages')
      await user.upload(passagesInput, passagesFile)
      
      const uploadButton = screen.getByText('Upload Files')
      await user.click(uploadButton)
      
      await waitFor(() => {
        expect(screen.getByText('Upload successful')).toBeInTheDocument()
      })
      
      // Then validate
      const validateButton = screen.getByText('Validate')
      await user.click(validateButton)
      
      await waitFor(() => {
        expect(screen.getByText('Validation successful')).toBeInTheDocument()
        expect(screen.getByText('Metadata')).toBeInTheDocument()
      })
    })

    it('handles validation errors', async () => {
      const mockResponse = {
        testdata_id: 'test-123',
        artifacts: ['passages'],
        counts: { passages: 10 }
      }
      mockApi.postTestdataUpload.mockResolvedValue(mockResponse)
      mockApi.getTestdataMeta.mockRejectedValue(new api.ApiError(404, 'Not found'))

      render(<TestDataPanel token={mockToken} />)
      
      // First upload some data
      const passagesFile = new File(['{"id":"1","text":"test"}'], 'passages.jsonl', { type: 'application/jsonl' })
      const passagesInput = screen.getByLabelText('Passages')
      await user.upload(passagesInput, passagesFile)
      
      const uploadButton = screen.getByText('Upload Files')
      await user.click(uploadButton)
      
      await waitFor(() => {
        expect(screen.getByText('Upload successful')).toBeInTheDocument()
      })
      
      // Then validate
      const validateButton = screen.getByText('Validate')
      await user.click(validateButton)
      
      await waitFor(() => {
        expect(screen.getByText('Not found')).toBeInTheDocument()
      })
    })
  })

  describe('Copy functionality', () => {
    it('copies testdata_id to clipboard', async () => {
      const mockResponse = {
        testdata_id: 'test-123',
        artifacts: ['passages'],
        counts: { passages: 10 }
      }
      mockApi.postTestdataUpload.mockResolvedValue(mockResponse)

      render(<TestDataPanel token={mockToken} />)
      
      const passagesFile = new File(['{"id":"1","text":"test"}'], 'passages.jsonl', { type: 'application/jsonl' })
      const passagesInput = screen.getByLabelText('Passages')
      await user.upload(passagesInput, passagesFile)
      
      const uploadButton = screen.getByText('Upload Files')
      await user.click(uploadButton)
      
      await waitFor(() => {
        expect(screen.getByText('Upload successful')).toBeInTheDocument()
      })
      
      const copyButton = screen.getByTitle('Copy to clipboard')
      await user.click(copyButton)
      
      // Check that the copy was successful (toast appears)
      await waitFor(() => {
        expect(screen.getByText('Copied to clipboard')).toBeInTheDocument()
      })
    })
  })
})
