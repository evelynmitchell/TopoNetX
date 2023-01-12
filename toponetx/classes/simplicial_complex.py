"""
Class for creation and manipulation of simplicial complexes.
The class also supports attaching arbitrary attributes and data to cells.
"""


try:
    from collections.abc import Iterable
except ImportError:
    from collections import Iterable

from itertools import combinations
from warnings import warn

import networkx as nx
import numpy as np
import scipy.sparse.linalg as spl
from hypernetx import Hypergraph
from networkx import Graph
from scipy.linalg import fractional_matrix_power
from scipy.sparse import coo_matrix, csr_matrix, diags, dok_matrix, eye
from sklearn.preprocessing import normalize

from toponetx.classes.node_view import NodeView
from toponetx.classes.ranked_entity import (
    DynamicCell,
    Node,
    RankedEntity,
    RankedEntitySet,
)
from toponetx.classes.simplex import Simplex, SimplexView
from toponetx.exception import TopoNetXError

try:
    from gudhi import SimplexTree
except ImportError:
    warn(
        "gudhi library is not installed."
        + " Default computing protocol will be set for 'normal'.\n"
        + " gudhi can be installed using: 'pip install gudhi'",
        stacklevel=2,
    )


# from toponetx.classes.cell_complex import CellComplex
# from toponetx.classes.combinatorial_complex import CombinatorialComplex
# from toponetx.classes.dynamic_combinatorial_complex import DynamicCombinatorialComplex

__all__ = ["SimplicialComplex"]


class SimplicialComplex:
    """Class representing a simplicial complex.

    Class for construction boundary operators, Hodge Laplacians,
    higher order (co)adjacency operators from collection of
    simplices.

    A simplicial complex is a topological space of a specific kind, constructed by
    "gluing together" points, line segments, triangles, and their higher-dimensional
    counterparts. It is a generalization of the notion of a triangle in a triangulated surface,
    or a tetrahedron in a tetrahedralized 3-dimensional manifold. Simplicial complexes are the
    basic objects of study in combinatorial topology.

    For example, a triangle is a simplicial complex because it is a collection of three
    points that are connected to each other in a specific way. Similarly, a tetrahedron is a
    simplicial complex because it is a collection of four points that are connected to each
    other in a specific way. These simplices can be thought of as the "building blocks" of a
    simplicial complex, and the complex itself is constructed by combining these building blocks
    in a specific way. For example, a 2-dimensional simplicial complex could be a collection of
    triangles that are connected to each other to form a surface, while a 3-dimensional simplicial
    complex could be a collection of tetrahedra that are connected to each other to form a solid object.

    The SimplicialComplex class is a class for representing simplicial complexes,
    which are a type of topological space constructed by "gluing together" points, line segments,
    triangles, and higher-dimensional counterparts. The class provides methods for computing boundary
    operators, Hodge Laplacians, and higher-order adjacency operators on the simplicial complex.
    It also allows for compatibility with the NetworkX and gudhi libraries.

    main features:
    --------------
    1. The SimplicialComplex class allows for the dynamic construction of simplicial complexes,
        enabling users to add or remove simplices from the complex after its initial creation.
    2. The class provides methods for computing boundary operators, Hodge Laplacians,
        and higher-order adjacency operators on the simplicial complex.
    3. The class is compatible with the gudhi library, allowing users to leverage the powerful
        algorithms and data structures provided by this package.
    4. The class supports the attachment of arbitrary attributes and data to simplices,
        enabling users to store and manipulate additional information about these objects.
    5. The class has robust error handling and input validation, ensuring reliable and easy use of the class.

    Parameters
    ----------
    -simplices : list, optional,  default: None
                list of maximal simplices that define the simplicial complex
    -name : hashable, optional, default: None
        If None then a placeholder '' will be inserted as name
    -mode : string, optional, default 'normal'.
        computational mode, available options are "normal" or "gudhi".
        default is 'normal'.

        Note : When ghudi is selected additioanl structure
        obtained from the simplicial tree is stored.
        this creates an additional reduannt storage
        but it can be used for access the simplicial
        tree of the complex.


    Note:
    -----
    A simplicial complex is determined by its maximal simplices, simplices that are not
    contained in any other simplices. If a maximal simplex is inserted, all faces of this
    simplex will be inserted automatically.

    Examples
    -------
    Example 1
        # defining a simplicial complex using a set of maximal simplices.
        >>> sc = SimplicialComplex([[1, 2, 3], [2, 3, 5], [0, 1]])

    Example 2
        # compatabiltiy with networkx
        >>> graph = Graph() # networkx graph
        >>> graph.add_edge(0, 1, weight=4)
        >>> graph.add_edge(0, 3)
        >>> graph.add_edge(0, 4)
        >>> graph.add_edge(1, 4)
        >>> sc = SimplicialComplex(simplices=graph)
        >>> sc.add_simplex([1, 2, 3])
        >>> sc.simplices
    """

    def __init__(self, simplices=None, name=None, mode="normal", **attr):

        self.mode = mode
        if name is None:
            self.name = ""
        else:
            self.name = name

        self._simplex_set = SimplexView()

        self.complex = dict()  # dictionary for simplicial complex attributes

        if simplices is not None:

            if not isinstance(simplices, Iterable):
                raise TypeError(
                    f"Input simplices must be given as Iterable, got {type(simplices)}."
                )

        if isinstance(simplices, Graph):

            _simplices = []
            for simplex in simplices:  # simplices is a networkx graph
                _simplices.append(([simplex], simplices.nodes[simplex]))
            for edge in simplices.edges:
                u, v = edge
                _simplices.append((edge, simplices.get_edge_data(u, v)))

            simplices = []
            for simplex in _simplices:
                s1 = Simplex(simplex[0], **simplex[1])
                simplices.append(s1)

        if self.mode == "gudhi":
            try:
                from gudhi import SimplexTree
            except ImportError:
                warn(
                    "gudhi library is not installed."
                    + "normal mode will be used for computations",
                    stacklevel=2,
                )

        if self.mode == "normal":
            if simplices is not None:
                if isinstance(simplices, Iterable):
                    self._simplex_set.add_simplices_from(simplices)

        elif self.mode == "gudhi":

            self.st = SimplexTree()
            if simplices is not None:

                if isinstance(simplices, Iterable):
                    for simplex in simplices:
                        self.st.insert(simplex)
                    self._simplex_set.build_faces_dict_from_gudhi_tree(self.st)

        else:
            raise ValueError(f" Import modes must be 'normal' and 'gudhi', got {mode}")

    @property
    def shape(self):
        """
        (number of simplices[i], for i in range(0,dim(Sc))  )

        Returns
        -------
        tuple

        """
        if len(self._simplex_set.faces_dict) == 0:
            print("Simplicial Complex is empty.")
        else:
            return [
                len(self._simplex_set.faces_dict[i])
                for i in range(len(self._simplex_set.faces_dict))
            ]

    @property
    def dim(self):
        """
        dimension of the simplicial complex is the highest dimension of any simplex in the complex
        """
        return self._simplex_set.max_dim

    @property
    def maxdim(self):
        """
        dimension of the simplicial complex is the highest dimension of any simplex in the complex
        """
        return self._simplex_set.max_dim

    @property
    def nodes(self):
        return NodeView(self._simplex_set.faces_dict, cell_type=Simplex)

    @property
    def simplices(self):
        """
        set of all simplices
        """
        return self._simplex_set

    def get_simplex_id(self, simplex):
        if simplex in self:
            return self[simplex]["id"]

    def is_maximal(self, simplex):
        if simplex in self:
            return self[simplex]["is_maximal"]

    def get_maximal_simplices_of_simplex(self, simplex):
        return self[simplex]["membership"]

    def skeleton(self, rank):
        """
        Returns
        -------
        set of simplices of dimesnsion n
        """
        if rank < len(self._simplex_set.faces_dict):
            return sorted(tuple(i) for i in self._simplex_set.faces_dict[rank].keys())
            # return list(self._simplex_set.faces_dict[n].keys())
        if rank < 0:
            raise ValueError(f"input must be a postive integer, got {rank}")
        raise ValueError(f"input {rank} exceeds max dim")

    def __str__(self):
        """
        String representation of SC

        Returns
        -------
        str

        """
        return f"Simplicial Complex with shape {self.shape} and dimension {self.dim}"

    def __repr__(self):
        """
        String representation of simplicial complex

        Returns
        -------
        str

        """
        return f"SimplicialComplex(name={self.name})"

    def __len__(self):
        """
        Number of simplices

        Returns
        -------
        int, total number of simplices in all dimensions
        """
        return np.sum(self.shape)

    def __getitem__(self, simplex):
        if simplex in self:
            return self._simplex_set[simplex]
        else:
            raise KeyError("simplex is not in the simplicial complex")

    def __setitem__(self, simplex, **attr):
        if simplex in self:
            self._simplex_set.__setitem__(simplex, **attr)
        else:
            raise KeyError("simplex is not in the simplicial complex")

    def __iter__(self):
        """
        Iterate over all faces of the simplicial complex

        Returns
        -------
        dict_keyiterator

        """

        all_simplices = []
        for i in range(len(self._simplex_set.faces_dict)):
            all_simplices = all_simplices + list(self._simplex_set.faces_dict[i].keys())
        return iter(all_simplices)

    def __contains__(self, item):
        """
        Returns boolean indicating if item is in self.face_set

        Parameters
        ----------
        item : tuple, list

        """
        return item in self._simplex_set

    @staticmethod
    def get_boundaries(simplices, min_dim=None, max_dim=None):
        """
        Parameters
        ----------
        simplices : list
            DESCRIPTION. list or of simplices, typically integers.
        min_dim : int, constrain the max dimension of faces
        max_dim : int, constrain the max dimension of faces
        Returns
        -------
        face_set : set
            DESCRIPTION. list of tuples or all faces at all levels (subsets) of the input list of simplices
        """

        if not isinstance(simplices, Iterable):
            raise TypeError(
                f"Input simplices must be given as a list or tuple, got {type(simplices)}."
            )

        face_set = set()
        for simplex in simplices:
            numnodes = len(simplex)
            for r in range(numnodes, 0, -1):
                for face in combinations(simplex, r):
                    if max_dim is None and min_dim is None:
                        face_set.add(frozenset(sorted(face)))
                    elif max_dim is not None and min_dim is not None:
                        if len(face) <= max_dim + 1 and len(face) >= min_dim + 1:
                            face_set.add(frozenset(sorted(face)))
                    elif max_dim is not None and min_dim is None:
                        if len(face) <= max_dim + 1:
                            face_set.add(frozenset(sorted(face)))
                    elif max_dim is None and min_dim is not None:
                        if len(face) >= min_dim + 1:
                            face_set.add(frozenset(sorted(face)))

        return face_set

    def remove_maximal_simplex(self, simplex):
        self._simplex_set.remove_maximal_simplex(simplex)

    def add_node(self, node, **attr):
        self._simplex_set.insert_node(node, **attr)

    def add_simplex(self, simplex, **attr):
        self._simplex_set.insert_simplex(simplex, **attr)

    def add_simplices_from(self, simplices):
        for s in simplices:
            self.add_simplex(s)

    def get_cofaces(self, simplex, codimension):
        """
        Parameters
        ----------
        simplex : list, tuple or simplex
            DESCRIPTION. the n simplex represented by a list of its nodes
        codimension : int
            DESCRIPTION. The codimension. If codimension = 0, all cofaces are returned


        Returns
        -------
        TYPE
            list of tuples(simplex).


        """
        entire_tree = self.get_boundaries(
            self.get_maximal_simplices_of_simplex(simplex)
        )
        return [
            i
            for i in entire_tree
            if frozenset(simplex).issubset(i) and len(i) - len(simplex) >= codimension
        ]

    def get_star(self, simplex):
        """
        Parameters
        ----------
        simplex : list, tuple or simplex
            DESCRIPTION. the n simplex represented by a list of its nodes


        Returns
        -------
        TYPE
            list of tuples(simplex),

        Note : return of this function is
            same as get_cofaces(simplex,0) .

        """
        return self.get_cofaces(simplex, 0)

    def set_simplex_attributes(self, values, name=None):
        """

            Parameters
            ----------
            values : TYPE
                DESCRIPTION.
            name : TYPE, optional
                DESCRIPTION. The default is None.

            Returns
            -------
            None.

            Example
            ------

            After computing some property of the simplex of a simplicial complex, you may want
            to assign a simplex attribute to store the value of that property for
            each simplex:

            >>> sc = SimplicialComplex()
            >>> sc.add_simplex([1, 2, 3, 4])
            >>> sc.add_simplex([1, 2, 4])
            >>> sc.add_simplex([3, 4, 8])
            >>> d = {(1, 2, 3): 'red', (1, 2, 4): 'blue'}
            >>> sc.set_simplex_attributes(d, name='color')
            >>> SC[(1, 2, 3)]['color']
            'red'

        If you provide a dictionary of dictionaries as the second argument,
        the entire dictionary will be used to update simplex attributes::

            Examples
            --------
            >>> sc = SimplicialComplex()
            >>> sc.add_simplex([1, 3, 4])
            >>> sc.add_simplex([1, 2, 3])
            >>> sc.add_simplex([1, 2, 4])
            >>> d = {(1, 3, 4): {'color': 'red', 'attr2': 1}, (1, 2, 4): {'color': 'blue', 'attr2': 3}}
            >>> sc.set_simplex_attributes(d)
            >>> SC[(1, 3, 4)]['color']
            'red'

        Note : If the dict contains simplices that are not in `self.simplices`, they are
        silently ignored.

        """

        if name is not None:
            # if `values` is a dict using `.items()` => {simplex: value}

            for simplex, value in values.items():
                try:
                    self[simplex][name] = value
                except KeyError:
                    pass

        else:

            for simplex, d in values.items():
                try:
                    self[simplex].update(d)
                except KeyError:
                    pass
            return

    def get_node_attributes(self, name):
        """Get node attributes from combintorial complex
        Parameters
        ----------
        name : string
           Attribute name
        Returns
        -------
        Dictionary of attributes keyed by node.

        Examples
        --------
            >>> sc = SimplicialComplex()
            >>> sc.add_simplex([1, 2, 3, 4])
            >>> sc.add_simplex([1, 2, 4])
            >>> sc.add_simplex([3, 4, 8])
            >>> d = {(1): 'red', (2): 'blue', (3): 'black'}
            >>> sc.set_simplex_attributes(d, name='color')
            >>> sc.get_node_attributes('color')
            >>>
        'blue'

        """
        return {tuple(n): self[n][name] for n in self.skeleton(0) if name in self[n]}

    def get_simplex_attributes(self, name, rank=None):
        """Get node attributes from simplical complex

        Parameters
        ----------
        name : string
           Attribute name
        rank : integer rank of the cell

        Returns
        -------
        Dictionary of attributes keyed by cell or k-cells of (rank=k) if rank is not None

        Examples
        --------
            >>> sc = SimplicialComplex()
            >>> sc.add_simplex([1, 2, 3, 4])
            >>> sc.add_simplex([1, 2, 4])
            >>> sc.add_simplex([3, 4, 8])
            >>> d={(1,2):'red',(2,3):'blue',(3,4):"black"}
            >>> sc.set_simplex_attributes(d,name='color')
            >>> sc.get_simplex_attributes('color')

        """
        if rank is None:
            return {n: self[n][name] for n in self if name in self[n]}
        return {n: self[n][name] for n in self.skeleton(rank) if name in self[n]}

    @staticmethod
    def get_edges_from_matrix(matrix):
        """
        Parameters
        ----------
        matrix : numpy or scipy array

        Returns
        -------
        edges : list of indices where the operator is not zero

        Rational:
        -------
         Most operaters (e.g. adjacencies/(co)boundary maps) that describe
         connectivity of the simplicial complex
         can be described as a graph whose nodes are the simplices used to
         construct the operator and whose edges correspond to the entries
         in the matrix where the operator is not zero.

         This property implies that many computations on simplicial complexes
         can be reduced to graph computations.

        """
        rows, cols = np.where(np.sign(np.abs(matrix)) > 0)
        edges = zip(rows.tolist(), cols.tolist())
        return edges

    # ---------- operators ---------------#

    def incidence_matrix(self, rank, signed=True, weight=None, index=False):
        """Compute incidence matrix of the simplicial complex.

        Getting the matrix that correpodnds to the boundary matrix of the input sc.

        Examples
        --------
            >>> sc = SimplicialComplex()
            >>> sc.add_simplex([1, 2, 3, 4])
            >>> sc.add_simplex([1, 2, 4])
            >>> sc.add_simplex([3, 4, 8])
            >>> B1 = sc.incidence_matrix(1)
            >>> B2 = sc.incidence_matrix(2)

        """
        if rank <= 0:
            raise ValueError(f"input dimension d must be larger than zero, got {rank}")
        if rank > self.dim:
            raise ValueError(
                f"input dimenion cannat be larger than the dimension of the complex, got {rank}"
            )

        if rank == 0:
            boundary = dok_matrix(
                (1, len(self._simplex_set.faces_dict[rank].items())), dtype=np.float32
            )
            boundary[0, 0 : len(self._simplex_set.faces_dict[rank].items())] = 1
            return boundary.tocsr()
        idx_simplices, idx_faces, values = [], [], []

        simplex_dict_d = {simplex: i for i, simplex in enumerate(self.skeleton(rank))}
        simplex_dict_d_minus_1 = {
            simplex: i for i, simplex in enumerate(self.skeleton(rank - 1))
        }
        for simplex, idx_simplex in simplex_dict_d.items():
            # for simplex, idx_simplex in self._simplex_set.faces_dict[d].items():
            for i, left_out in enumerate(np.sort(list(simplex))):
                idx_simplices.append(idx_simplex)
                values.append((-1) ** i)
                face = frozenset(simplex).difference({left_out})
                idx_faces.append(simplex_dict_d_minus_1[tuple(face)])
        assert len(values) == (rank + 1) * len(simplex_dict_d)
        boundary = coo_matrix(
            (values, (idx_faces, idx_simplices)),
            dtype=np.float32,
            shape=(
                len(simplex_dict_d_minus_1),
                len(simplex_dict_d),
            ),
        )
        if index:
            if signed:
                return (
                    list(simplex_dict_d_minus_1.keys()),
                    list(simplex_dict_d.keys()),
                    boundary,
                )
            else:
                return (
                    list(simplex_dict_d_minus_1.keys()),
                    list(simplex_dict_d.keys()),
                    abs(boundary),
                )
        else:
            if signed:
                return boundary
            else:
                return abs(boundary)

    def coincidence_matrix(self, rank, signed=True, weight=None, index=False):
        """Compute coincidence matrix of the simplicial complex.

        This is also called the coboundary matrix.
        """
        if index:
            idx_faces, idx_simplices, boundary = self.incidence_matrix(
                rank, signed=signed, weight=weight, index=index
            ).T
            return idx_faces, idx_simplices, boundary.T
        else:
            return self.incidence_matrix(
                rank, signed=signed, weight=weight, index=index
            ).T

    def hodge_laplacian_matrix(self, rank, signed=True, weight=None, index=False):
        """Compute hodge-laplacian matrix for the simplicial complex

        Parameters
        ----------
        d : int, dimension of the Laplacian matrix.

        signed : bool, is true return absolute value entry of the Laplacian matrix
                       this is useful when one needs to obtain higher-order
                       adjacency matrices from the hodge-laplacian
                       typically higher-order adjacency matrices' entries are
                       typically positive.

        weight : bool, default=False

        index : boolean, optional, default False
                indicates wheather to return the indices that define the incidence matrix

        Returns
        -------
        Laplacian : scipy.sparse.csr.csr_matrix

        when index is true:
            return also a list : list

        Examples
        --------
        >>> sc = SimplicialComplex()
        >>> sc.add_simplex([1, 2, 3, 4])
        >>> sc.add_simplex([1, 2, 4])
        >>> sc.add_simplex([3, 4, 8])
        >>> L1 = sc.hodge_laplacian_matrix(1)
        """
        if rank == 0:
            row, column, inc_next = self.incidence_matrix(
                rank + 1, weight=weight, index=True
            )
            lap = inc_next @ inc_next.transpose()
            if not signed:
                lap = abs(lap)
            if index:
                return row, lap
            else:
                return lap
        elif rank < self.dim:
            row, column, inc_next = self.incidence_matrix(
                rank + 1, weight=weight, index=True
            )
            row, column, inc = self.incidence_matrix(rank, weight=weight, index=True)
            lap = inc_next @ inc_next.transpose() + inc.transpose() @ inc
            if not signed:
                lap = abs(lap)
            if index:
                return column, lap
            else:
                return lap

        elif rank == self.dim:
            row, column, inc = self.incidence_matrix(rank, weight=weight, index=True)
            lap = inc.transpose() @ inc
            if not signed:
                lap = abs(lap)
            if index:
                return column, lap
            else:
                return lap

        else:
            raise ValueError(
                f"Rank should be larger than 0 and <= {self.dim} (maximal dimension simplices), got {rank}"
            )
        if not signed:
            lap = abs(lap)
        else:
            return abs(lap)

    def normalized_laplacian_matrix(self, rank, weight=None):
        r"""Return the normalized hodge Laplacian matrix of graph.

        The normalized hodge Laplacian is the matrix

        .. math::
            N_d = D^{-1/2} L_d D^{-1/2}

        where `L` is the simplicial complex Laplacian and `D` is the diagonal matrix of
        simplices of rank d.

        Parameters
        ----------
        rank : int
            Rank of the hodge laplacian matrix
        weight : string or None, optional (default='weight')
            The edge data key used to compute each value in the matrix.
            If None, then each edge has weight 1.

        Returns
        -------
        _ : Scipy sparse matrix
            The normalized hodge Laplacian matrix.

        Example 1
        ---------
        >>> sc = SimplicialComplex([[1, 2, 3], [2, 3, 5], [0, 1]])
        >>> norm_lap1 = sc.normalized_laplacian_matrix(1)
        >>> norm_lap1
        """
        import numpy as np
        import scipy as sp
        import scipy.sparse  # call as sp.sparse

        hodge_lap = self.hodge_laplacian_matrix(rank)
        m, n = hodge_lap.shape
        diags_ = abs(hodge_lap).sum(axis=1)

        with sp.errstate(divide="ignore"):
            diags_sqrt = 1.0 / np.sqrt(diags_)
        diags_sqrt[np.isinf(diags_sqrt)] = 0
        diags_sqrt = sp.sparse.csr_array(
            sp.sparse.spdiags(diags_sqrt.T, 0, m, n, format="csr")
        )

        return sp.sparse.csr_matrix(diags_sqrt @ (hodge_lap @ diags_sqrt))

    def up_laplacian_matrix(self, rank, signed=True, weight=None, index=False):
        """Compute the up Laplacian matrix of the simplicial complex.

        Parameters
        ----------
        rank : int, rank of the up Laplacian matrix.

        signed : bool, is true return absolute value entry of the Laplacian matrix
                       this is useful when one needs to obtain higher-order
                       adjacency matrices from the hodge-laplacian
                       typically higher-order adjacency matrices' entries are
                       typically positive.
        weight : bool, default=False
            If False all nonzero entries are 1.
            If True and self.static all nonzero entries are filled by
            self.cells.cell_weight dictionary values.
        index : boolean, optional, default False
            list identifying rows with nodes,edges or cells used to index the hodge Laplacian matrix
            depending on the input dimension

        Returns
        -------
        up Laplacian : scipy.sparse.csr.csr_matrix

        when index is true:
            return also a list : list
            list identifying rows with nodes,edges or cells used to index the hodge Laplacian matrix
            depending on the input dimension
        """

        weight = None  # this feature is not supported in this version

        if rank == 0:
            row, col, inc_next = self.incidence_matrix(
                rank + 1, weight=weight, index=True
            )
            lap_up = inc_next @ inc_next.transpose()
        elif rank < self.maxdim:
            row, col, inc_next = self.incidence_matrix(
                rank + 1, weight=weight, index=True
            )
            lap_up = inc_next @ inc_next.transpose()
        else:
            raise ValueError(
                f"Rank should larger than 0 and <= {self.maxdim-1} (maximal dimension cells-1), got {rank}"
            )
        if not signed:
            lap_up = abs(lap_up)

        if index:
            return row, lap_up
        return lap_up

    def down_laplacian_matrix(self, rank, signed=True, weight=None, index=False):
        """Compute the down Laplacian matrix of the simplicial complex.

        Parameters
        ----------
        rank : int
            Rank of the down Laplacian matrix.
        signed : bool
            is true return absolute value entry of the Laplacian matrix
            this is useful when one needs to obtain higher-order
            adjacency matrices from the hodge-laplacian
            typically higher-order adjacency matrices' entries are
            typically positive.
        weight : bool, default=False
            If False all nonzero entries are 1.
            If True and self.static all nonzero entries are filled by
            self.cells.cell_weight dictionary values.
        index : boolean, optional, default False
            list identifying rows with simplices used to index the hodge Laplacian matrix
            depending on the input dimension.

        Returns
        -------
        down Laplacian : scipy.sparse.csr.csr_matrix

        when index is true:
            return also a list : list
            list identifying rows with simplices used to index the hodge Laplacian matrix
            depending on the input dimension
        """
        weight = None  # this feature is not supported in this version

        if rank <= self.maxdim and rank > 0:
            row, column, inc = self.incidence_matrix(rank, weight=weight, index=True)
            lap_down = inc.transpose() @ inc
        else:
            raise ValueError(
                f"Rank should be larger than 1 and <= {self.maxdim} (maximal dimension cells), got {rank}."
            )
        if not signed:
            lap_down = abs(lap_down)
        if index:
            return column, lap_down
        return lap_down

    def adjacency_matrix(self, rank, signed=False, weight=None, index=False):
        """Compute the adjacency matrix of the simplicial complex.

        The method takes a rank parameter, which is the rank of the simplicial complex,
        and two optional parameters: signed and weight. The signed parameter determines whether
        the adjacency matrix should be signed or unsigned, and the weight parameter allows for
        specifying weights for the edges in the adjacency matrix. The index parameter determines
        whether the method should return the matrix indices along with the adjacency matrix.

        Examples
        --------
        >>> sc = SimplicialComplex()
        >>> sc.add_simplex([1, 2, 3, 4])
        >>> sc.add_simplex([1, 2, 4])
        >>> sc.add_simplex([3, 4, 8])
        >>> adj1 = sc.adjacency_matrix(1)
        """
        weight = None  # this feature is not supported in this version

        ind, lap_up = self.up_laplacian_matrix(
            rank, signed=signed, weight=weight, index=True
        )
        lap_up.setdiag(0)

        if not signed:
            lap_up = abs(lap_up)
        if index:
            return ind, lap_up
        return lap_up

    def coadjacency_matrix(self, rank, signed=False, weight=None, index=False):
        """Compute the coadjacency matrix of the simplicial complex."""
        weight = None  # this feature is not supported in this version

        ind, lap_down = self.down_laplacian_matrix(
            rank, signed=signed, weight=weight, index=True
        )
        lap_down.setdiag(0)
        if not signed:
            lap_down = abs(lap_down)
        if index:
            return ind, lap_down
        return lap_down

    def k_hop_incidence_matrix(self, rank, k):
        """Compute the k-hop incidence matrix of the simplicial complex."""
        inc = self.incidence_matrix(rank, signed=True)
        if rank < self.dim and rank >= 0:
            adj = self.adjacency_matrix(rank, signed=True)
        if rank <= self.dim and rank > 0:
            coadj = self.coadjacency_matrix(rank, signed=True)
        if rank == self.dim:
            return inc @ np.power(coadj, k)
        if rank == 0:
            return inc @ np.power(adj, k)
        return inc @ np.power(adj, k) + inc @ np.power(coadj, k)

    def k_hop_coincidence_matrix(self, rank, k):
        """Compute the k-hop coincidence matrix of the simplicial complex."""
        coinc = self.coincidence_matrix(rank, signed=True)
        if rank < self.dim and rank >= 0:
            adj = self.adjacency_matrix(rank, signed=True)
        if rank <= self.dim and rank > 0:
            coadj = self.coadjacency_matrix(rank, signed=True)
        if rank == self.dim:
            return np.power(coadj, k) @ coinc
        if rank == 0:
            return np.power(adj, k) @ coinc
        return np.power(adj, k) @ coinc + np.power(coadj, k) @ coinc

    def add_elements_from_nx_graph(self, graph):
        _simplices = []
        for edge in graph.edges:
            _simplices.append(edge)
        for node in graph.nodes:
            _simplices.append([node])

        self.add_simplices_from(_simplices)

    def restrict_to_simplices(self, cell_set, name=None):
        """
        Constructs a simplicial complex using a subset of the simplices
        in simplicial complex

        Parameters
        ----------
        cell_set: iterable of hashables or simplices
            A subset of elements of the simplicial complex

        name: str, optional

        Returns
        -------
        new simplicial Complex : SimplicialComplex

        Example

        >>> c1 = Simplex((1, 2, 3))
        >>> c2 = Simplex((1, 2, 4))
        >>> c3 = Simplex((1, 2, 5))
        >>> sc = SimplicialComplex([c1, c2, c3])
        >>> sc1 = sc.restrict_to_simplices([c1, (2, 4)])
        >>> sc1.simplices

        """
        rns = []
        for cell in cell_set:
            if cell in self:
                rns.append(cell)

        sc = SimplicialComplex(simplices=rns, name=name)

        return sc

    def restrict_to_nodes(self, node_set, name=None):
        """
        Constructs a new simplicial complex  by restricting the simplices in the
        simplicial complex to the nodes referenced by node_set.

        Parameters
        ----------
        node_set: iterable of hashables
            References a subset of elements of self.nodes

        name: string, optional, default: None

        Returns
        -------
        new Simplicial Complex : SimplicialComplex

        Example
        >>> c1 = Simplex((1, 2, 3))
        >>> c2 = Simplex((1, 2, 4))
        >>> c3 = Simplex((1, 2, 5))
        >>> sc = SimplicialComplex([c1, c2, c3])
        >>> sc.restrict_to_nodes([1, 2, 3, 4])

        """

        simplices = []
        node_set = set(node_set)
        for rank in range(1, self.dim + 1):
            for s in self.skeleton(rank):
                if s.issubset(node_set):
                    simplices.append(s)
        all_sim = simplices + list(
            [frozenset({i}) for i in node_set if i in self.nodes]
        )

        return SimplicialComplex(all_sim, name=name)

    def get_all_maximal_simplices(self):
        """
        Example
        >>> c1 = Simplex((1, 2, 3))
        >>> c2 = Simplex((1, 2, 4))
        >>> c3 = Simplex((2, 5))
        >>> sc = SimplicialComplex([c1, c2, c3])
        >>> sc.get_all_maximal_simplices()
        """
        maxmimals = []
        for s in self:
            if self.is_maximal(s):
                maxmimals.append(tuple(s))
        return maxmimals

    @staticmethod
    def from_spharpy(mesh):
        """
        >>> import spharapy.trimesh as tm
        >>> import spharapy.spharabasis as sb
        >>> import spharapy.datasets as sd
        >>> mesh = tm.TriMesh([[0, 1, 2]], [[1., 0., 0.], [0., 2., 0.],
        ...                                        [0., 0., 3.]])

        >>> sc = SimplicialComplex.from_spharpy(mesh)

        """

        vertices = np.array(mesh.vertlist)
        sc = SimplicialComplex(mesh.trilist)

        first_ind = np.min(mesh.trilist)

        if first_ind == 0:

            sc.set_simplex_attributes(
                dict(zip(range(len(vertices)), vertices)), name="position"
            )
        else:  # first index starts at 1.

            sc.set_simplex_attributes(
                dict(zip(range(first_ind, len(vertices) + first_ind), vertices)),
                name="position",
            )

        return sc

    @staticmethod
    def from_gudhi(tree):
        """
        >>> from gudhi import SimplexTree
        >>> tree = SimplexTree()
        >>> tree.insert([1,2,3,5])
        >>> sc = SimplicialComplex.from_gudhi(tree)
        """
        sc = SimplicialComplex()
        sc._simplex_set.build_faces_dict_from_gudhi_tree(tree)
        return sc

    @staticmethod
    def from_trimesh(mesh):
        """
        >>> import trimesh
        >>> mesh = trimesh.Trimesh(vertices=[[0, 0, 0], [0, 0, 1], [0, 1, 0]],
                               faces=[[0, 1, 2]],
                               process=False)
        >>> sc = SimplicialComplex.from_trimesh(mesh)
        >>> print(sc.nodes0)
        >>> print(sc.simplices)
        >>> sc[(0)]['position']

        """
        # try to see the index of the first vertex

        sc = SimplicialComplex(mesh.faces)

        first_ind = np.min(mesh.faces)

        if first_ind == 0:

            sc.set_simplex_attributes(
                dict(zip(range(len(mesh.vertices)), mesh.vertices)), name="position"
            )
        else:  # first index starts at 1.

            sc.set_simplex_attributes(
                dict(
                    zip(range(first_ind, len(mesh.vertices) + first_ind), mesh.vertices)
                ),
                name="position",
            )

        return sc

    @staticmethod
    def load_mesh(file_path, process=False, force=None):
        """

        Parameters
        ----------

            file_path: str, the source of the data to be loadeded

            process : bool, trimesh will try to process the mesh before loading it.

            force: (str or None)
                options: 'mesh' loader will "force" the result into a mesh through concatenation
                         None : will not force the above.

        Return
        -------
            SimplicialComplex
                the output simplicial complex stores the same structure stored in the mesh input file.

        Note:
        -------
            mesh files supported : obj, off, glb


        >>> sc = SimplicialComplex.load_mesh("C:/temp/stanford-bunny.obj")

        >>> sc.nodes

        """
        import trimesh

        mesh = trimesh.load_mesh(file_path, process=process, force=None)
        return SimplicialComplex.from_trimesh(mesh)

    def is_triangular_mesh(self):

        if self.dim <= 2:

            lst = self.get_all_maximal_simplices()
            for i in lst:
                if len(i) == 2:  # gas edges that are not part of a face
                    return False
            return True
        else:
            return False

    def to_trimesh(self, vertex_position_name="position"):

        import trimesh

        if not self.is_triangular_mesh():
            raise TopoNetXError(
                "input simplicial complex has dimension higher than 2 and hence it cannot be converted to a trimesh object"
            )
        else:

            vertices = list(
                dict(
                    sorted(self.get_node_attributes(vertex_position_name).items())
                ).values()
            )

            return trimesh.Trimesh(
                faces=self.get_all_maximal_simplices(), vertices=vertices, process=False
            )

    def to_spharapy(self, vertex_position_name="position"):

        """
        >>> import spharapy.trimesh as tm
        >>> import spharapy.spharabasis as sb
        >>> import spharapy.datasets as sd
        >>> mesh = tm.TriMesh([[0, 1, 2]],[[0, 0, 0], [0, 0, 1], [0, 1, 0]] )
        >>> sc = SimplicialComplex.from_spharpy(mesh)
        >>> mesh2 = sc.to_spharapy()
        >>> mesh2.vertlist == mesh.vertlist
        >>> mesh2.trilist == mesh.trilist
        """

        import spharapy.trimesh as tm

        if not self.is_triangular_mesh():
            raise TopoNetXError(
                "input simplicial complex has dimension higher than 2 and hence it cannot be converted to a trimesh object"
            )

        else:

            vertices = list(
                dict(
                    sorted(self.get_node_attributes(vertex_position_name).items())
                ).values()
            )

            return tm.TriMesh(self.get_all_maximal_simplices(), vertices)

    def laplace_beltrami_operator(self, mode="inv_euclidean"):

        """Compute a laplacian matrix for a triangular mesh
        The method creates a laplacian matrix for a triangular
        mesh using different weighting function.
        Parameters
        ----------
        mode : {'unit', 'inv_euclidean', 'half_cotangent'}, optional
            The methods for determining the edge weights. Using the option
            'unit' all edges of the mesh are weighted by unit weighting
            function, the result is an adjacency matrix. The option
            'inv_euclidean' results in edge weights corresponding to the
            inverse Euclidean distance of the edge lengths. The option
            'half_cotangent' uses the half of the cotangent of the two angles
            opposed to an edge as weighting function. the default weighting
            function is 'inv_euclidean'.
        Returns
        -------
        laplacianmatrix : array, shape (n_vertices, n_vertices)
            Matrix, which contains the discrete laplace operator for data
            defined at the vertices of a triangular mesh. The number of
            vertices of the triangular mesh is n_points.

        """

        mesh = self.to_spharapy()
        return mesh.laplacianmatrix(mode=mode)

    @staticmethod
    def from_nx_graph(graph):
        """
        Examples
        --------
        >>> graph = nx.Graph()  # or DiGraph, MultiGraph, MultiDiGraph, etc
        >>> graph.add_edge('1', '2', weight=2)
        >>> graph.add_edge('3', '4', weight=4)
        >>> sc = SimplicialComplex.from_nx_graph(graph)
        >>> sc[('1','2')]['weight']
        """
        return SimplicialComplex(graph, name=graph.name)

    def is_connected(self):
        """Check if the simplicial complex is connected.

        Note: a simplicial complex is connected iff its 1-skeleton graph is connected.

        """
        graph = nx.Graph()
        for edge in self.skeleton(1):
            edge = list(edge)
            graph.add_edge(edge[0], edge[1])
        for node in self.skeleton(0):
            graph.add_node(list(node)[0])
        return nx.is_connected(graph)

    def to_cell_complex(self):
        """Convert a simplicial complex to a cell complex.

        Example
        -------
        >>> c1 = Simplex((1, 2, 3))
        >>> c2 = Simplex((1, 2, 4))
        >>> c3 = Simplex((2, 5))
        >>> sc = SimplicialComplex([c1, c2, c3])
        >>> sc.to_cell_complex()
        """
        from toponetx.classes.cell_complex import CellComplex

        return CellComplex(self.get_all_maximal_simplices())

    def to_hypergraph(self):
        """Convert a simplicial complex to a hypergraph.

        Example
        -------
        >>> c1= Simplex((1, 2, 3))
        >>> c2= Simplex((1, 2, 4))
        >>> c3= Simplex((2, 5))
        >>> sc = SimplicialComplex([c1, c2, c3])
        >>> sc.to_hypergraph()
        """
        graph = []
        for rank in range(1, self.dim + 1):
            edge = [list(cell) for cell in self.skeleton(rank)]
            graph = graph + edge
        return Hypergraph(graph, static=True)

    def to_combinatorial_complex(self, dynamic=True):
        """Convert a simplicial complex to a combinatorial complex.

        Parameters
        ----------
        dynamic: bool, optional, default is false
            when True returns DynamicCombinatorialComplex
            when False returns CombinatorialComplex

        Example
        -------
        >>> c1 = Simplex((1, 2, 3))
        >>> c2 = Simplex((1, 2, 3))

        >>> c3 = Simplex((1, 2, 4))
        >>> c4 = Simplex((2, 5))
        >>> sc = SimplicialComplex([c1, c2, c3])
        >>> CC = sc.to_combinatorial_complex()
        """

        from toponetx.classes.combinatorial_complex import CombinatorialComplex
        from toponetx.classes.dynamic_combinatorial_complex import (
            DynamicCombinatorialComplex,
        )

        if dynamic:
            graph = []
            for rank in range(1, self.dim + 1):
                edge = [
                    DynamicCell(elements=list(cell), rank=len(cell) - 1, **self[cell])
                    for cell in self.skeleton(rank)
                ]
                graph = graph + edge
            res = RankedEntitySet("", graph, safe_insert=False)
            return DynamicCombinatorialComplex(res)
        else:
            cc = CombinatorialComplex()
            for rank in range(1, self.dim + 1):
                for cell in self.skeleton(rank):
                    cc.add_cell(cell, rank=len(cell) - 1, **self[cell])
            return cc
