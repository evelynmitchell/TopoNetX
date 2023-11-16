"""Test normalization."""

import numpy as np
import scipy.sparse.linalg as spl
from scipy.sparse import csr_matrix, diags

from toponetx.utils.normalization import (
    _compute_B1_normalized_matrix,
    _compute_B1T_normalized_matrix,
    _compute_B2_normalized_matrix,
    _compute_B2T_normalized_matrix,
    _compute_D1,
    _compute_D2,
    _compute_D3,
    _compute_D5,
    compute_bunch_normalized_matrices,
    compute_kipf_adjacency_normalized_matrix,
    compute_laplacian_normalized_matrix,
    compute_x_laplacian_normalized_matrix,
    compute_xu_asymmetric_normalized_matrix,
)


def test_compute_laplacian_normalized_matrix():
    """Test normalize laplacian."""
    adjacency_matrix = np.array(
        [
            [0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            [1.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0, 1.0],
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        ]
    )

    # Calculate the degree matrix
    degree_matrix = np.diag(adjacency_matrix.sum(axis=1))

    # Calculate the Laplacian matrix
    L = np.array(degree_matrix - adjacency_matrix)

    L = csr_matrix(L).asfptype()
    normalized_L = compute_laplacian_normalized_matrix(L)
    expected_result = np.array(
        [
            [0.5, -0.25, 0.0, 0.0, 0.0, -0.25],
            [-0.25, 0.5, -0.25, 0.0, 0.0, 0.0],
            [0.0, -0.25, 0.5, -0.25, 0.0, 0.0],
            [0.0, 0.0, -0.25, 0.5, -0.25, 0.0],
            [0.0, 0.0, 0.0, -0.25, 0.5, -0.25],
            [-0.25, 0.0, 0.0, 0.0, -0.25, 0.5],
        ]
    )
    assert np.allclose(normalized_L.toarray(), expected_result.toarray())


def test_compute_x_laplacian_normalized_matrix():
    """Test normalize up or down laplacian."""
    L = csr_matrix([[2.0, -1.0, 0.0], [-1.0, 3.0, -1.0], [0.0, -1.0, 2.0]])
    Lx = csr_matrix([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]])
    normalized_Lx = compute_x_laplacian_normalized_matrix(L, Lx)
    expected_result = csr_matrix([[0.25, 0.0, 0.0], [0.0, 0.0, 0.25], [0.0, 0.25, 0.0]])
    assert np.allclose(normalized_Lx.toarray(), expected_result.toarray())

    # Test case 2
    L = csr_matrix([[4.0, 0], [0.0, 4.0]])
    Lx = csr_matrix([[0.0, 1.0], [1.0, 0.0]])
    normalized_Lx = compute_x_laplacian_normalized_matrix(L, Lx)
    expected_result = np.array([[0.0, 0.25], [0.25, 0.0]])
    assert np.allclose(normalized_Lx.toarray(), expected_result.toarray())


def test_compute_kipf_adjacency_normalized_matrix():
    """Test kipf_adjacency_matrix_normalization."""
    # Test case 1
    A_opt = np.array(
        [
            [0, 1, 0, 0, 0, 1],
            [1, 0, 1, 0, 0, 0],
            [0, 1, 0, 1, 0, 0],
            [0, 0, 1, 0, 1, 0],
            [0, 0, 0, 1, 0, 1],
            [1, 0, 0, 0, 1, 0],
        ]
    )
    normalized_A_opt = compute_kipf_adjacency_normalized_matrix(csr_matrix(A_opt))
    expected_result = np.array(
        [
            [0.0, 0.5, 0.0, 0.0, 0.0, 0.5],
            [0.5, 0.0, 0.5, 0.0, 0.0, 0.0],
            [0.0, 0.5, 0.0, 0.5, 0.0, 0.0],
            [0.0, 0.0, 0.5, 0.0, 0.5, 0.0],
            [0.0, 0.0, 0.0, 0.5, 0.0, 0.5],
            [0.5, 0.0, 0.0, 0.0, 0.5, 0.0],
        ]
    )

    assert np.allclose(normalized_A_opt.toarray(), expected_result.toarray())

    normalized_A_opt = compute_kipf_adjacency_normalized_matrix(
        csr_matrix(A_opt), add_identity=True
    )
    expected_result = np.array(
        [
            [0.33333333, 0.33333333, 0.0, 0.0, 0.0, 0.33333333],
            [0.33333333, 0.33333333, 0.33333333, 0.0, 0.0, 0.0],
            [0.0, 0.33333333, 0.33333333, 0.33333333, 0.0, 0.0],
            [0.0, 0.0, 0.33333333, 0.33333333, 0.33333333, 0.0],
            [0.0, 0.0, 0.0, 0.33333333, 0.33333333, 0.33333333],
            [0.33333333, 0.0, 0.0, 0.0, 0.33333333, 0.33333333],
        ]
    )
    assert np.allclose(normalized_A_opt.toarray(), expected_result.toarray())


def test_compute_bunch_normalized_matrices():
    """Unit tests for bunch_normalization function."""
    # Test case 1: Normalization with numpy arrays
    B1 = np.array([[1, 0, 1], [0, 1, 1], [1, 1, 0]])
    B2 = np.array([[1, 0, 1], [0, 1, 0], [1, 1, 1]])
    B1N, B1TN, B2N, B2TN = compute_bunch_normalized_matrices(B1, B2)

    assert np.allclose(
        B1N,
        np.array([[0.1, 0.0, 0.1], [0.0, 0.125, 0.125], [0.16666667, 0.16666667, 0.0]]),
    )

    assert np.allclose(
        B1TN,
        np.array([[0.2, 0.0, 0.33333333], [0.0, 0.125, 0.16666667], [0.3, 0.375, 0.0]]),
    )

    assert np.allclose(
        B2N,
        np.array(
            [
                [0.33333333, 0.0, 0.33333333],
                [0.0, 0.33333333, 0.0],
                [0.33333333, 0.33333333, 0.33333333],
            ]
        ),
    )

    assert np.allclose(
        B2TN,
        np.array(
            [[0.5, 0.0, 0.33333333], [0.0, 1.0, 0.33333333], [0.5, 0.0, 0.33333333]]
        ),
    )

    # Test case 2: Normalization with scipy coo_matrices
    B1 = csr_matrix([[1, 0, 1], [0, 1, 1], [1, 1, 0]])
    B2 = csr_matrix([[1, 0, 1], [0, 1, 0], [1, 1, 1]])
    B1N, B1TN, B2N, B2TN = compute_bunch_normalized_matrices(B1, B2)

    assert np.allclose(
        B1N.toarray(),
        np.array([[0.1, 0.0, 0.1], [0.0, 0.125, 0.125], [0.16666667, 0.16666667, 0.0]]),
    )

    assert np.allclose(
        B1TN.toarray(),
        np.array([[0.2, 0.0, 0.33333333], [0.0, 0.125, 0.16666667], [0.3, 0.375, 0.0]]),
    )

    assert np.allclose(
        B2N.toarray(),
        np.array(
            [
                [0.33333333, 0.0, 0.33333333],
                [0.0, 0.33333333, 0.0],
                [0.33333333, 0.33333333, 0.33333333],
            ]
        ),
    )

    assert np.allclose(
        B2TN.toarray(),
        np.array(
            [[0.5, 0.0, 0.33333333], [0.0, 1.0, 0.33333333], [0.5, 0.0, 0.33333333]]
        ),
    )
