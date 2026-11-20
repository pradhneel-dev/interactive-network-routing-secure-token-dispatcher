import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, api: { ...real.api, additive: vi.fn(), backoff: vi.fn(), fibonacci: vi.fn(), concepts: vi.fn().mockResolvedValue([{ term: 'Walk', meaning: 'repeats allowed' }]) } }
})
import { api } from '../api'
import MathLab from '../components/MathLab'

beforeAll(() => {
  class RO { observe() {} unobserve() {} disconnect() {} }
  vi.stubGlobal('ResizeObserver', RO)
})
beforeEach(() => vi.clearAllMocks())

describe('Math Lab', () => {
  it('model selector swaps inputs and results are computed from the current inputs', async () => {
    vi.mocked(api.additive).mockResolvedValue({ model: 'additive', formula: 'T_n = T_(n-1) + k', sequence: [100, 125, 150], unit: 'packets', assumptions: 'fixed k' })
    vi.mocked(api.backoff).mockResolvedValue({ model: 'backoff', formula: 'D_n = min(r x D_(n-1), cap)', sequence: [100, 200, 300, 300], unit: 'ms', assumptions: 'capped', capped_at_retry: 2 })
    const user = userEvent.setup()
    render(<MathLab />)
    expect(screen.getByLabelText(/Increment k/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    await waitFor(() => expect(screen.getByTestId('sequence')).toHaveTextContent('T0=100, T1=125, T2=150'))
    expect(api.additive).toHaveBeenCalledWith(100, 25, 10)

    await user.selectOptions(screen.getByLabelText('Select model'), 'backoff')
    expect(screen.queryByLabelText(/Increment k/)).not.toBeInTheDocument()
    await user.type(screen.getByLabelText(/Cap/), '300')
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    await waitFor(() => expect(screen.getByTestId('formula')).toHaveTextContent('min(r x D_(n-1), cap)'))
    expect(api.backoff).toHaveBeenCalledWith(100, 2, 8, 300)
    expect(screen.getByTestId('chart')).toBeInTheDocument()
    expect(screen.getByText(/Cap reached at retry 2/)).toBeInTheDocument()
  })
  it('shows backend validation errors', async () => {
    const { ApiError } = await import('../api')
    vi.mocked(api.fibonacci).mockRejectedValue(new ApiError('Number of steps must be a non-negative integer.', 'invalid_input', 400))
    const user = userEvent.setup()
    render(<MathLab />)
    await user.selectOptions(screen.getByLabelText('Select model'), 'fibonacci')
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('non-negative')
  })
  it('explains walk vs path vs route', async () => {
    const user = userEvent.setup()
    render(<MathLab />)
    await user.selectOptions(screen.getByLabelText('Select model'), 'concepts')
    expect(await screen.findByText('repeats allowed')).toBeInTheDocument()
  })
})
