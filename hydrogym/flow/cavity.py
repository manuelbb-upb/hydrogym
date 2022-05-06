import numpy as np
import firedrake as fd
from firedrake import dx, ds
from firedrake.petsc import PETSc

import ufl
from ufl import sym, curl, dot, inner, nabla_grad, div, cos, sin, atan_2

from ..core import FlowConfig

class Cavity(FlowConfig):
    from .mesh.cavity import INLET, FREESTREAM, OUTLET, SLIP, WALL
    def __init__(self, h5_file=None, Re=5000):
        """
        controller(t, y) -> omega
        y = (CL, CD)
        omega = scalar rotation rate
        """
        from .mesh.cavity import load_mesh
        mesh = load_mesh()

        self.Re = fd.Constant(ufl.real(Re))
        self.U_inf = fd.Constant((1.0, 0.0))
        super().__init__(mesh, h5_file=h5_file)

    def init_bcs(self, mixed=False):
        V, Q = self.function_spaces(mixed=mixed)

        # Define actual boundary conditions
        self.bcu_inflow = fd.DirichletBC(V, self.U_inf, self.INLET)
        self.bcu_freestream = fd.DirichletBC(V.sub(1), fd.Constant(0.0), self.FREESTREAM)
        self.bcu_noslip = fd.DirichletBC(V, fd.interpolate(fd.Constant((0, 0)), V), self.WALL)
        self.bcu_slip = fd.DirichletBC(V.sub(1), fd.Constant(0.0), self.SLIP)  # Free-slip
        self.bcp_outflow = fd.DirichletBC(Q, fd.Constant(0), self.OUTLET)

        self.bcu_slip = None
        raise NotImplementedError  # Still need to add slip boundary

    def collect_bcu(self):
        return [self.bcu_inflow, self.bcu_freestream, self.bcu_noslip, self.bcu_slip]
    
    def collect_bcp(self):
        return [self.bcp_outflow]

    def compute_forces(self, u, p):
        # Lift/drag on cylinder
        force = -dot(self.sigma(u, p), self.n)
        CL = [fd.assemble(2*force[1]*ds(cyl)) for cyl in self.CYLINDER]
        CD = [fd.assemble(2*force[0]*ds(cyl)) for cyl in self.CYLINDER]
        return CL, CD