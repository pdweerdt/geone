#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Python module:  'geosclassicinterface.py'
author:         Julien Straubhaar
date:           jun-2021

Module interfacing classical geostatistics for python (estimation and simulation
based on simple and ordinary kriging).
"""

import numpy as np
import sys, os
import copy
import multiprocessing

from geone import img
from geone.geosclassic_core import geosclassic
from geone import covModel as gcm
from geone.img import Img, PointSet

version = [geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER]

# ----------------------------------------------------------------------------
def img_py2C(im_py):
    """
    Converts an image from python to C.

    Parameters
    ----------
    im_py : :class:`geone.img.Img`
        image in python

    Returns
    -------
    im_c : (MPDS_IMAGE *)
        image in C
    """
    fname = 'img_py2C'

    im_c = geosclassic.malloc_MPDS_IMAGE()
    geosclassic.MPDSInitImage(im_c)

    err = geosclassic.MPDSMallocImage(im_c, im_py.nxyz(), im_py.nv)
    if err:
        print(f'ERROR ({fname}): can not convert image from python to C')
        return None

    im_c.grid.nx = im_py.nx
    im_c.grid.ny = im_py.ny
    im_c.grid.nz = im_py.nz

    im_c.grid.sx = im_py.sx
    im_c.grid.sy = im_py.sy
    im_c.grid.sz = im_py.sz

    im_c.grid.ox = im_py.ox
    im_c.grid.oy = im_py.oy
    im_c.grid.oz = im_py.oz

    im_c.grid.nxy = im_py.nxy()
    im_c.grid.nxyz = im_py.nxyz()

    im_c.nvar = im_py.nv

    im_c.nxyzv = im_py.nxyz() * im_py.nv

    for i in range(im_py.nv):
        geosclassic.mpds_set_varname(im_c.varName, i, im_py.varname[i])
        # geosclassic.charp_array_setitem(im_c.varName, i, im_py.varname[i]) # does not work!

    v = im_py.val.reshape(-1)
    np.putmask(v, np.isnan(v), geosclassic.MPDS_MISSING_VALUE)
    geosclassic.mpds_set_real_vector_from_array(im_c.var, 0, v)
    np.putmask(v, v == geosclassic.MPDS_MISSING_VALUE, np.nan) # replace missing_value by np.nan (restore) (v is not a copy...)

    return im_c
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def img_C2py(im_c):
    """
    Converts an image from C to python.

    Parameters
    ----------
    im_c : (MPDS_IMAGE *)
        image in C

    Returns
    -------
    im_py : :class:`geone.img.Img`
        image in python
    """
    nxyz = im_c.grid.nx * im_c.grid.ny * im_c.grid.nz
    nxyzv = nxyz * im_c.nvar

    varname = [geosclassic.mpds_get_varname(im_c.varName, i) for i in range(im_c.nvar)]
    # varname = [geosclassic.charp_array_getitem(im_c.varName, i) for i in range(im_c.nvar)] # also works

    v = np.zeros(nxyzv)
    geosclassic.mpds_get_array_from_real_vector(im_c.var, 0, v)

    im_py = Img(nx=im_c.grid.nx, ny=im_c.grid.ny, nz=im_c.grid.nz,
                sx=im_c.grid.sx, sy=im_c.grid.sy, sz=im_c.grid.sz,
                ox=im_c.grid.ox, oy=im_c.grid.oy, oz=im_c.grid.oz,
                nv=im_c.nvar, val=v, varname=varname)

    np.putmask(im_py.val, im_py.val == geosclassic.MPDS_MISSING_VALUE, np.nan)

    return im_py
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def ps_py2C(ps_py):
    """
    Converts an image from python to C.

    Parameters
    ----------
    ps_py : :class:`geone.img.PointSet`
        point set in python

    Returns
    -------
    ps_c : (MPDS_POINTSET *)
        point set in C
    """
    fname = 'ps_py2C'

    if ps_py.nv < 4:
        print(f'ERROR ({fname}): point set (python) have less than 4 variables')
        return None

    nvar = ps_py.nv - 3

    ps_c = geosclassic.malloc_MPDS_POINTSET()
    geosclassic.MPDSInitPointSet(ps_c)

    err = geosclassic.MPDSMallocPointSet(ps_c, ps_py.npt, nvar)
    if err:
        print(f'ERROR ({fname}): can not convert point set from python to C')
        return None

    ps_c.npoint = ps_py.npt
    ps_c.nvar = nvar

    for i in range(nvar):
        geosclassic.mpds_set_varname(ps_c.varName, i, ps_py.varname[i+3])

    geosclassic.mpds_set_real_vector_from_array(ps_c.x, 0, ps_py.val[0].reshape(-1))
    geosclassic.mpds_set_real_vector_from_array(ps_c.y, 0, ps_py.val[1].reshape(-1))
    geosclassic.mpds_set_real_vector_from_array(ps_c.z, 0, ps_py.val[2].reshape(-1))

    v = ps_py.val[3:].reshape(-1)
    np.putmask(v, np.isnan(v), geosclassic.MPDS_MISSING_VALUE)
    geosclassic.mpds_set_real_vector_from_array(ps_c.var, 0, v)
    np.putmask(v, v == geosclassic.MPDS_MISSING_VALUE, np.nan)  # replace missing_value by np.nan (restore) (v is not a copy...)

    return ps_c
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def ps_C2py(ps_c):
    """
    Converts an image from C to python.

    Parameters
    ----------
    ps_c : (MPDS_POINTSET *)
        point set in C

    Returns
    -------
    ps_py : :class:`geone.img.PointSet`
        point set in python
    """
    varname = ['X', 'Y', 'Z'] + [geosclassic.mpds_get_varname(ps_c.varName, i) for i in range(ps_c.nvar)]

    v = np.zeros(ps_c.npoint*ps_c.nvar)
    geosclassic.mpds_get_array_from_real_vector(ps_c.var, 0, v)

    # coord = np.zeros(ps_c.npoint)
    # geosclassic.mpds_get_array_from_real_vector(ps_c.z, 0, coord)
    # v = np.hstack(coord,v)
    # geosclassic.mpds_get_array_from_real_vector(ps_c.y, 0, coord)
    # v = np.hstack(coord,v)
    # geosclassic.mpds_get_array_from_real_vector(ps_c.x, 0, coord)
    # v = np.hstack(coord,v)

    cx = np.zeros(ps_c.npoint)
    cy = np.zeros(ps_c.npoint)
    cz = np.zeros(ps_c.npoint)
    geosclassic.mpds_get_array_from_real_vector(ps_c.x, 0, cx)
    geosclassic.mpds_get_array_from_real_vector(ps_c.y, 0, cy)
    geosclassic.mpds_get_array_from_real_vector(ps_c.z, 0, cz)
    v = np.hstack((cx, cy, cz, v))

    ps_py = PointSet(npt=ps_c.npoint,
                     nv=ps_c.nvar+3, val=v, varname=varname)

    np.putmask(ps_py.val, ps_py.val == geosclassic.MPDS_MISSING_VALUE, np.nan)

    return ps_py
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def covModel1Delem_py2C(covModelElem_py, nx, ny, nz, sx, sy, sz, ox, oy, oz):
    """
    Converts an elementary covariance model 1D from python to C.

    Simulation grid geometry is specified in case of non-stationary covariance
    model.

    Parameters
    ----------
    covModelElem_py : 2-tuple
        elementary covariance model 1D in python, `covModelElem_py`=(t, d),
        with:
        - t : str
            type of elementary covariance model, can be
            - 'nugget'         (see function `geone.covModel.cov_nug`)
            - 'spherical'      (see function `geone.covModel.cov_sph`)
            - 'exponential'    (see function `geone.covModel.cov_exp`)
            - 'gaussian'       (see function `geone.covModel.cov_gau`)
            - 'linear'         (see function `geone.covModel.cov_lin`)
            - 'cubic'          (see function `geone.covModel.cov_cub`)
            - 'sinus_cardinal' (see function `geone.covModel.cov_sinc`)
            - 'gamma'          (see function `geone.covModel.cov_gamma`)
            - 'power'          (see function `geone.covModel.cov_pow`)
            - 'exponential_generalized' (see function `geone.covModel.cov_exp_gen`)
            - 'matern'         (see function `geone.covModel.cov_matern`)
        - d : dict
            dictionary of required parameters to be passed to the elementary
            model `t` (value can be a "single value" or an array that matches
            the dimension of the simulation grid (for non-stationary
            covariance model)
        e.g.
        - (t, d) = ('spherical', {'w':2.0, 'r':1.5})
        - (t, d) = ('power', {'w':2.0, 'r':1.5, 's':1.7})
        - (t, d) = ('matern', {'w':2.0, 'r':1.5, 'nu':1.5})
    nx, ny, nz : int
        number of grid cells along each axis
    sx, sy, sz : float
        cell size along each axis
    ox, oy, oz : float
        origin of the grid (bottom-lower-left corner)

    Returns
    -------
    covModelElem_c : (MPDS_COVMODELELEM *)
        elementary covariance model in C
    flag : bool
        indicates if the conversion has succeeded (True) or failed (False)
    """
    fname = 'covModel1Delem_py2C'

    covModelElem_c = geosclassic.malloc_MPDS_COVMODELELEM()
    geosclassic.MPDSGeosClassicInitCovModelElem(covModelElem_c)

    w_flag = True   # weight to be set if True
    r_flag = True   # ranges to be set if True
    s_flag = False  # s (additional parameter) to be set if True

    # type
    if covModelElem_py[0] == 'nugget':
        covModelElem_c.covModelType = geosclassic.COV_NUGGET
        r_flag = False
    elif covModelElem_py[0] == 'spherical':
        covModelElem_c.covModelType = geosclassic.COV_SPHERICAL
    elif covModelElem_py[0] == 'exponential':
        covModelElem_c.covModelType = geosclassic.COV_EXPONENTIAL
    elif covModelElem_py[0] == 'gaussian':
        covModelElem_c.covModelType = geosclassic.COV_GAUSSIAN
    elif covModelElem_py[0] == 'linear':
        covModelElem_c.covModelType = geosclassic.COV_LINEAR
    elif covModelElem_py[0] == 'cubic':
        covModelElem_c.covModelType = geosclassic.COV_CUBIC
    elif covModelElem_py[0] == 'sinus_cardinal':
        covModelElem_c.covModelType = geosclassic.COV_SINUS_CARDINAL
    elif covModelElem_py[0] == 'gamma':
        covModelElem_c.covModelType = geosclassic.COV_GAMMA
        s_flag = True
        s_name = 's'
    elif covModelElem_py[0] == 'power':
        covModelElem_c.covModelType = geosclassic.COV_POWER
        s_flag = True
        s_name = 's'
    elif covModelElem_py[0] == 'exponential_generalized':
        covModelElem_c.covModelType = geosclassic.COV_EXPONENTIAL_GENERALIZED
        s_flag = True
        s_name = 's'
    elif covModelElem_py[0] == 'matern':
        covModelElem_c.covModelType = geosclassic.COV_MATERN
        s_flag = True
        s_name = 'nu'

    # weight
    if w_flag:
        param = covModelElem_py[1]['w']
        if np.size(param) == 1:
            covModelElem_c.weightImageFlag = geosclassic.FALSE
            covModelElem_c.weightValue = float(param)
        else:
            covModelElem_c.weightImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel1D from python to C ('w' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.weightImage = img_py2C(im)

    # ranges
    if r_flag:
        # ... range rx
        param = covModelElem_py[1]['r']
        if np.size(param) == 1:
            covModelElem_c.rxImageFlag = geosclassic.FALSE
            covModelElem_c.rxValue = float(param)
        else:
            covModelElem_c.rxImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel1D from python to C ('r(x)' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.rxImage = img_py2C(im)
        # ... range ry
        covModelElem_c.ryImageFlag = geosclassic.FALSE
        covModelElem_c.ryValue = 0.0
        # ... range rz
        covModelElem_c.rzImageFlag = geosclassic.FALSE
        covModelElem_c.rzValue = 0.0

    # s (additional parameter)
    if s_flag:
        param = covModelElem_py[1][s_name]
        if np.size(param) == 1:
            covModelElem_c.sImageFlag = geosclassic.FALSE
            covModelElem_c.sValue = float(param)
        else:
            covModelElem_c.sImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel1D from python to C ('s' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.sImage = img_py2C(im)

    return covModelElem_c, True
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def covModel2Delem_py2C(covModelElem_py, nx, ny, nz, sx, sy, sz, ox, oy, oz):
    """
    Converts an elementary covariance model 2D from python to C.

    Simulation grid geometry is specified in case of non-stationary covariance
    model.

    Parameters
    ----------
    covModelElem_py : 2-tuple
        elementary covariance model 2D in python, `covModelElem_py`=(t, d),
        with:
        - t : str
            type of elementary covariance model, can be
            - 'nugget'         (see function `geone.covModel.cov_nug`)
            - 'spherical'      (see function `geone.covModel.cov_sph`)
            - 'exponential'    (see function `geone.covModel.cov_exp`)
            - 'gaussian'       (see function `geone.covModel.cov_gau`)
            - 'linear'         (see function `geone.covModel.cov_lin`)
            - 'cubic'          (see function `geone.covModel.cov_cub`)
            - 'sinus_cardinal' (see function `geone.covModel.cov_sinc`)
            - 'gamma'          (see function `geone.covModel.cov_gamma`)
            - 'power'          (see function `geone.covModel.cov_pow`)
            - 'exponential_generalized' (see function `geone.covModel.cov_exp_gen`)
            - 'matern'         (see function `geone.covModel.cov_matern`)
        - d : dict
            dictionary of required parameters to be passed to the elementary
            model `t` (value can be a "single value" or an array that matches
            the dimension of the simulation grid (for non-stationary
            covariance model)
        e.g.
        - (t, d) = ('spherical', {'w':2.0, 'r':[1.5, 2.5]})
        - (t, d) = ('power', {'w':2.0, 'r':[1.5, 2.5], 's':1.7})
        - (t, d) = ('matern', {'w':2.0, 'r':[1.5, 2.5], 'nu':1.5})
    nx, ny, nz : int
        number of grid cells along each axis
    sx, sy, sz : float
        cell size along each axis
    ox, oy, oz : float
        origin of the grid (bottom-lower-left corner)

    Returns
    -------
    covModelElem_c : (MPDS_COVMODELELEM *)
        elementary covariance model in C
    flag : bool
        indicates if the conversion has succeeded (True) or failed (False)
    """
    fname = 'covModel2Delem_py2C'

    covModelElem_c = geosclassic.malloc_MPDS_COVMODELELEM()
    geosclassic.MPDSGeosClassicInitCovModelElem(covModelElem_c)

    w_flag = True   # weight to be set if True
    r_flag = True   # ranges to be set if True
    s_flag = False  # s (additional parameter) to be set if True

    # type
    if covModelElem_py[0] == 'nugget':
        covModelElem_c.covModelType = geosclassic.COV_NUGGET
        r_flag = False
    elif covModelElem_py[0] == 'spherical':
        covModelElem_c.covModelType = geosclassic.COV_SPHERICAL
    elif covModelElem_py[0] == 'exponential':
        covModelElem_c.covModelType = geosclassic.COV_EXPONENTIAL
    elif covModelElem_py[0] == 'gaussian':
        covModelElem_c.covModelType = geosclassic.COV_GAUSSIAN
    elif covModelElem_py[0] == 'linear':
        covModelElem_c.covModelType = geosclassic.COV_LINEAR
    elif covModelElem_py[0] == 'cubic':
        covModelElem_c.covModelType = geosclassic.COV_CUBIC
    elif covModelElem_py[0] == 'sinus_cardinal':
        covModelElem_c.covModelType = geosclassic.COV_SINUS_CARDINAL
    elif covModelElem_py[0] == 'gamma':
        covModelElem_c.covModelType = geosclassic.COV_GAMMA
        s_flag = True
        s_name = 's'
    elif covModelElem_py[0] == 'power':
        covModelElem_c.covModelType = geosclassic.COV_POWER
        s_flag = True
        s_name = 's'
    elif covModelElem_py[0] == 'exponential_generalized':
        covModelElem_c.covModelType = geosclassic.COV_EXPONENTIAL_GENERALIZED
        s_flag = True
        s_name = 's'
    elif covModelElem_py[0] == 'matern':
        covModelElem_c.covModelType = geosclassic.COV_MATERN
        s_flag = True
        s_name = 'nu'

    # weight
    if w_flag:
        param = covModelElem_py[1]['w']
        if np.size(param) == 1:
            covModelElem_c.weightImageFlag = geosclassic.FALSE
            covModelElem_c.weightValue = float(param)
        else:
            covModelElem_c.weightImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel2D from python to C ('w' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.weightImage = img_py2C(im)

    # ranges
    if r_flag:
        # ... range rx
        param = covModelElem_py[1]['r'][0]
        if np.size(param) == 1:
            covModelElem_c.rxImageFlag = geosclassic.FALSE
            covModelElem_c.rxValue = float(param)
        else:
            covModelElem_c.rxImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel2D from python to C ('r(x)' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.rxImage = img_py2C(im)
        # ... range ry
        param = covModelElem_py[1]['r'][1]
        if np.size(param) == 1:
            covModelElem_c.ryImageFlag = geosclassic.FALSE
            covModelElem_c.ryValue = float(param)
        else:
            covModelElem_c.ryImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel2D from python to C ('r(y)' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.ryImage = img_py2C(im)
        # ... range rz
        covModelElem_c.rzImageFlag = geosclassic.FALSE
        covModelElem_c.rzValue = 0.0

    # s (additional parameter)
    if s_flag:
        param = covModelElem_py[1][s_name]
        if np.size(param) == 1:
            covModelElem_c.sImageFlag = geosclassic.FALSE
            covModelElem_c.sValue = float(param)
        else:
            covModelElem_c.sImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel2D from python to C ('s' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.sImage = img_py2C(im)

    return covModelElem_c, True
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def covModel3Delem_py2C(covModelElem_py, nx, ny, nz, sx, sy, sz, ox, oy, oz):
    """
    Converts an elementary covariance model 3D from python to C.

    Simulation grid geometry is specified in case of non-stationary covariance
    model.

    Parameters
    ----------
    covModelElem_py : 2-tuple
        elementary covariance model 3D in python, `covModelElem_py`=(t, d),
        with:
        - t : str
            type of elementary covariance model, can be
            - 'nugget'         (see function `geone.covModel.cov_nug`)
            - 'spherical'      (see function `geone.covModel.cov_sph`)
            - 'exponential'    (see function `geone.covModel.cov_exp`)
            - 'gaussian'       (see function `geone.covModel.cov_gau`)
            - 'linear'         (see function `geone.covModel.cov_lin`)
            - 'cubic'          (see function `geone.covModel.cov_cub`)
            - 'sinus_cardinal' (see function `geone.covModel.cov_sinc`)
            - 'gamma'          (see function `geone.covModel.cov_gamma`)
            - 'power'          (see function `geone.covModel.cov_pow`)
            - 'exponential_generalized' (see function `geone.covModel.cov_exp_gen`)
            - 'matern'         (see function `geone.covModel.cov_matern`)
        - d : dict
            dictionary of required parameters to be passed to the elementary
            model `t` (value can be a "single value" or an array that matches
            the dimension of the simulation grid (for non-stationary
            covariance model)
        e.g.
        - (t, d) = ('spherical', {'w':2.0, 'r':[1.5, 2.5, 3.0]})
        - (t, d) = ('power', {'w':2.0, 'r':[1.5, 2.5, 3.0], 's':1.7})
        - (t, d) = ('matern', {'w':2.0, 'r':[1.5, 2.5, 3.0], 'nu':1.5})
    nx, ny, nz : int
        number of grid cells along each axis
    sx, sy, sz : float
        cell size along each axis
    ox, oy, oz : float
        origin of the grid (bottom-lower-left corner)

    Returns
    -------
    covModelElem_c : (MPDS_COVMODELELEM *)
        elementary covariance model in C
    flag : bool
        indicates if the conversion has succeeded (True) or failed (False)
    """
    fname = 'covModel3Delem_py2C'

    covModelElem_c = geosclassic.malloc_MPDS_COVMODELELEM()
    geosclassic.MPDSGeosClassicInitCovModelElem(covModelElem_c)

    w_flag = True   # weight to be set if True
    r_flag = True   # ranges to be set if True
    s_flag = False  # s (additional parameter) to be set if True

    # type
    if covModelElem_py[0] == 'nugget':
        covModelElem_c.covModelType = geosclassic.COV_NUGGET
        r_flag = False
    elif covModelElem_py[0] == 'spherical':
        covModelElem_c.covModelType = geosclassic.COV_SPHERICAL
    elif covModelElem_py[0] == 'exponential':
        covModelElem_c.covModelType = geosclassic.COV_EXPONENTIAL
    elif covModelElem_py[0] == 'gaussian':
        covModelElem_c.covModelType = geosclassic.COV_GAUSSIAN
    elif covModelElem_py[0] == 'linear':
        covModelElem_c.covModelType = geosclassic.COV_LINEAR
    elif covModelElem_py[0] == 'cubic':
        covModelElem_c.covModelType = geosclassic.COV_CUBIC
    elif covModelElem_py[0] == 'sinus_cardinal':
        covModelElem_c.covModelType = geosclassic.COV_SINUS_CARDINAL
    elif covModelElem_py[0] == 'gamma':
        covModelElem_c.covModelType = geosclassic.COV_GAMMA
        s_flag = True
        s_name = 's'
    elif covModelElem_py[0] == 'power':
        covModelElem_c.covModelType = geosclassic.COV_POWER
        s_flag = True
        s_name = 's'
    elif covModelElem_py[0] == 'exponential_generalized':
        covModelElem_c.covModelType = geosclassic.COV_EXPONENTIAL_GENERALIZED
        s_flag = True
        s_name = 's'
    elif covModelElem_py[0] == 'matern':
        covModelElem_c.covModelType = geosclassic.COV_MATERN
        s_flag = True
        s_name = 'nu'

    # weight
    if w_flag:
        param = covModelElem_py[1]['w']
        if np.size(param) == 1:
            covModelElem_c.weightImageFlag = geosclassic.FALSE
            covModelElem_c.weightValue = float(param)
        else:
            covModelElem_c.weightImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel3D from python to C ('w' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.weightImage = img_py2C(im)

    # ranges
    if r_flag:
        # ... range rx
        param = covModelElem_py[1]['r'][0]
        if np.size(param) == 1:
            covModelElem_c.rxImageFlag = geosclassic.FALSE
            covModelElem_c.rxValue = float(param)
        else:
            covModelElem_c.rxImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel3D from python to C ('r(x)' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.rxImage = img_py2C(im)
        # ... range ry
        param = covModelElem_py[1]['r'][1]
        if np.size(param) == 1:
            covModelElem_c.ryImageFlag = geosclassic.FALSE
            covModelElem_c.ryValue = float(param)
        else:
            covModelElem_c.ryImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel3D from python to C ('r(y)' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.ryImage = img_py2C(im)
        # ... range rz
        param = covModelElem_py[1]['r'][2]
        if np.size(param) == 1:
            covModelElem_c.rzImageFlag = geosclassic.FALSE
            covModelElem_c.rzValue = float(param)
        else:
            covModelElem_c.rzImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel3D from python to C ('r(z)' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.rzImage = img_py2C(im)

    # s (additional parameter)
    if s_flag:
        param = covModelElem_py[1][s_name]
        if np.size(param) == 1:
            covModelElem_c.sImageFlag = geosclassic.FALSE
            covModelElem_c.sValue = float(param)
        else:
            covModelElem_c.sImageFlag = geosclassic.TRUE
            try:
                param = np.asarray(param).reshape(nz, ny, nx)
            except:
                print(f"ERROR ({fname}): can not convert covModel3D from python to C ('s' not compatible with simulation grid)")
                return covModelElem_c, False
            im = Img(nx=nx, ny=ny, nz=nz,
                     sx=sx, sy=sy, sz=sz,
                     ox=ox, oy=oy, oz=oz,
                     nv=1, val=param)
            covModelElem_c.sImage = img_py2C(im)

    return covModelElem_c, True
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def covModel1D_py2C(covModel_py, nx, ny, nz, sx, sy, sz, ox, oy, oz):
    """
    Converts a covariance model 1D from python to C.

    Simulation grid geometry is specified in case of non-stationary covariance
    model.

    Parameters
    ----------
    covModel_py : :class:`geone.covModel.CovModel1D`
        covariance model 1D in python
    nx, ny, nz : int
        number of grid cells along each axis
    sx, sy, sz : float
        cell size along each axis
    ox, oy, oz : float
        origin of the grid (bottom-lower-left corner)

    Returns
    -------
    covModel_c : (MPDS_COVMODEL *)
        covariance model in C
    flag : bool
        indicates if the conversion has succeeded (True) or failed (False)
    """
    covModel_c = geosclassic.malloc_MPDS_COVMODEL()
    geosclassic.MPDSGeosClassicInitCovModel(covModel_c)

    n = len(covModel_py.elem)
    covModel_c.nelem = n
    covModel_c.covModelElem = geosclassic.new_MPDS_COVMODELELEM_array(n)
    for i, covModelElem in enumerate(covModel_py.elem):
        covModelElem_c, flag = covModel1Delem_py2C(covModelElem, nx, ny, nz, sx, sy, sz, ox, oy, oz)
        if flag:
            geosclassic.MPDS_COVMODELELEM_array_setitem(covModel_c.covModelElem, i, covModelElem_c)
        # geosclassic.free_MPDS_COVMODELELEM(covModelElem_c)
        if not flag:
            return covModel_c, False

    # covModel_c.angle1, covModel_c.angle2, covModel_c.angle3: keep to 0.0
    covModel_c.angle1 = 0.0
    covModel_c.angle2 = 0.0
    covModel_c.angle3 = 0.0

    return covModel_c, True
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def covModel2D_py2C(covModel_py, nx, ny, nz, sx, sy, sz, ox, oy, oz):
    """
    Converts a covariance model 2D from python to C.

    Simulation grid geometry is specified in case of non-stationary covariance
    model.

    Parameters
    ----------
    covModel_py : :class:`geone.covModel.CovModel2D`
        covariance model 2D in python
    nx, ny, nz : int
        number of grid cells along each axis
    sx, sy, sz : float
        cell size along each axis
    ox, oy, oz : float
        origin of the grid (bottom-lower-left corner)

    Returns
    -------
    covModel_c : (MPDS_COVMODEL *)
        covariance model in C
    flag : bool
        indicates if the conversion has succeeded (True) or failed (False)
    """
    fname = 'covModel2D_py2C'

    covModel_c = geosclassic.malloc_MPDS_COVMODEL()
    geosclassic.MPDSGeosClassicInitCovModel(covModel_c)

    n = len(covModel_py.elem)
    covModel_c.nelem = n
    covModel_c.covModelElem = geosclassic.new_MPDS_COVMODELELEM_array(n)
    for i, covModelElem in enumerate(covModel_py.elem):
        covModelElem_c, flag = covModel2Delem_py2C(covModelElem, nx, ny, nz, sx, sy, sz, ox, oy, oz)
        if flag:
            geosclassic.MPDS_COVMODELELEM_array_setitem(covModel_c.covModelElem, i, covModelElem_c)
        # geosclassic.free_MPDS_COVMODELELEM(covModelElem_c)
        if not flag:
            return covModel_c, False

    # covModel_c.angle2, covModel_c.angle3: keep to 0.0
    # angle1
    param = covModel_py.alpha
    if np.size(param) == 1:
        covModel_c.angle1ImageFlag = geosclassic.FALSE
        covModel_c.angle1Value = float(param)
    else:
        covModel_c.angle1ImageFlag = geosclassic.TRUE
        try:
            param = np.asarray(param).reshape(nz, ny, nx)
        except:
            print(f"ERROR ({fname}): can not convert covModel2D from python to C ('alpha' not compatible with simulation grid)")
            return covModel_c, False
        im = Img(nx=nx, ny=ny, nz=nz,
                 sx=sx, sy=sy, sz=sz,
                 ox=ox, oy=oy, oz=oz,
                 nv=1, val=param)
        covModel_c.angle1Image = img_py2C(im)
    # angle2
    covModel_c.angle2 = 0.0
    # angle3
    covModel_c.angle3 = 0.0

    return covModel_c, True
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def covModel3D_py2C(covModel_py, nx, ny, nz, sx, sy, sz, ox, oy, oz):
    """
    Converts a covariance model 3D from python to C.

    Simulation grid geometry is specified in case of non-stationary covariance
    model.

    Parameters
    ----------
    covModel_py : :class:`geone.covModel.CovModel3D`
        covariance model 3D in python
    nx, ny, nz : int
        number of grid cells along each axis
    sx, sy, sz : float
        cell size along each axis
    ox, oy, oz : float
        origin of the grid (bottom-lower-left corner)

    Returns
    -------
    covModel_c : (MPDS_COVMODEL *)
        covariance model in C
    flag : bool
        indicates if the conversion has succeeded (True) or failed (False)
    """
    fname = 'covModel3D_py2C'

    covModel_c = geosclassic.malloc_MPDS_COVMODEL()
    geosclassic.MPDSGeosClassicInitCovModel(covModel_c)

    n = len(covModel_py.elem)
    covModel_c.nelem = n
    covModel_c.covModelElem = geosclassic.new_MPDS_COVMODELELEM_array(n)
    for i, covModelElem in enumerate(covModel_py.elem):
        covModelElem_c, flag = covModel3Delem_py2C(covModelElem, nx, ny, nz, sx, sy, sz, ox, oy, oz)
        if flag:
            geosclassic.MPDS_COVMODELELEM_array_setitem(covModel_c.covModelElem, i, covModelElem_c)
        # geosclassic.free_MPDS_COVMODELELEM(covModelElem_c)
        if not flag:
            return covModel_c, False

    # angle1
    param = covModel_py.alpha
    if np.size(param) == 1:
        covModel_c.angle1ImageFlag = geosclassic.FALSE
        covModel_c.angle1Value = float(param)
    else:
        covModel_c.angle1ImageFlag = geosclassic.TRUE
        try:
            param = np.asarray(param).reshape(nz, ny, nx)
        except:
            print(f"ERROR ({fname}): can not convert covModel3D from python to C ('alpha' not compatible with simulation grid)")
            return covModel_c, False
        im = Img(nx=nx, ny=ny, nz=nz,
                 sx=sx, sy=sy, sz=sz,
                 ox=ox, oy=oy, oz=oz,
                 nv=1, val=param)
        covModel_c.angle1Image = img_py2C(im)
    # angle2
    param = covModel_py.beta
    if np.size(param) == 1:
        covModel_c.angle2ImageFlag = geosclassic.FALSE
        covModel_c.angle2Value = float(param)
    else:
        covModel_c.angle2ImageFlag = geosclassic.TRUE
        try:
            param = np.asarray(param).reshape(nz, ny, nx)
        except:
            print(f"ERROR ({fname}): can not convert covModel3D from python to C ('beta' not compatible with simulation grid)")
            return covModel_c, False
        im = Img(nx=nx, ny=ny, nz=nz,
                 sx=sx, sy=sy, sz=sz,
                 ox=ox, oy=oy, oz=oz,
                 nv=1, val=param)
        covModel_c.angle2Image = img_py2C(im)
    # angle3
    param = covModel_py.gamma
    if np.size(param) == 1:
        covModel_c.angle3ImageFlag = geosclassic.FALSE
        covModel_c.angle3Value = float(param)
    else:
        covModel_c.angle3ImageFlag = geosclassic.TRUE
        try:
            param = np.asarray(param).reshape(nz, ny, nx)
        except:
            print(f"ERROR ({fname}): can not convert covModel3D from python to C ('gamma' not compatible with simulation grid)")
            return covModel_c, False
        im = Img(nx=nx, ny=ny, nz=nz,
                 sx=sx, sy=sy, sz=sz,
                 ox=ox, oy=oy, oz=oz,
                 nv=1, val=param)
        covModel_c.angle3Image = img_py2C(im)

    return covModel_c, True
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor):
    """
    Converts geosclassic output from C to python.

    Parameters
    ----------
    mpds_geosClassicOutput : (MPDS_GEOSCLASSICOUTPUT *)
        geosclassic output in C
    mpds_progressMonitor : (MPDS_PROGRESSMONITOR *)
        progress monitor in C

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv` variables (output variables:
            simulations or estimates and standard deviations);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    # Initialization
    image = None
    nwarning, warnings = None, None

    image = img_C2py(mpds_geosClassicOutput.outputImage)

    nwarning = mpds_progressMonitor.nwarning
    warnings = []
    if mpds_progressMonitor.nwarningNumber:
        tmp = np.zeros(mpds_progressMonitor.nwarningNumber, dtype='intc') # 'intc' for C-compatibility
        geosclassic.mpds_get_array_from_int_vector(mpds_progressMonitor.warningNumberList, 0, tmp)
        warningNumberList = np.asarray(tmp, dtype='int') # 'int' or equivalently 'int64'
        for iwarn in warningNumberList:
            warning_message = geosclassic.mpds_get_warning_message(int(iwarn)) # int() required!
            warning_message = warning_message.replace('\n', '')
            warnings.append(warning_message)

    return {'image':image, 'nwarning':nwarning, 'warnings':warnings}
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def fill_mpds_geosClassicInput(
        space_dim,
        cov_model,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        outputReportFile,
        computationMode,
        dataImage,
        dataPointSet,
        mask,
        mean,
        var,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        nGibbsSamplerPathMin,
        nGibbsSamplerPathMax,
        seed,
        nreal):
    """
    Fills a mpds_geosClassicInput C structure from given parameters.

    This function should not be called directly, it is used in other functions
    of this module.

    Parameters
    ----------
    space_dim : int
        space dimension (1, 2, or 3)
    cov_model : :class:`geone.CovModel.CovModel<d>D`
        covariance model
    nx, ny, nz : ints
        number of grid cells along each axis
    sx, sy, sz : floats
        cell size along each axis
    ox, oy, oz : floats
        origin of the grid (bottom-lower-left corner)
    varname : str
        variable name
    outputReportFile : bool
        indicates if a report file is desired
    computationMode : int
        computation mode:
        - `computationMode=0`: estimation, ordinary kriging
        - `computationMode=1`: estimation, simple kriging
        - `computationMode=2`: simulation, ordinary kriging
        - `computationMode=3`: simulation, simple kriging
    dataImage : sequence of :class:`geone.img.Img`, or None
        list of data image(s)
    dataPointSet : sequence of :class:`geone.img.PointSet`, or None
        list of data point set(s)
    mask : array-like, or None
        mask value in grid cells
    mean : float, or array-like, or None
        mean value in grid cells
    var : float, or array-like, or None
        variance value in grid cells
    searchRadiusRelative : float
        searchRadiusRelative parameter
    nneighborMax : int
        nneighborMax parameter
    searchNeighborhoodSortMode : int
        searchNeighborhoodSortMode parameter
    nGibbsSamplerPathMin : int
        nGibbsSamplerPathMin parameter
    nGibbsSamplerPathMax : int
        nGibbsSamplerPathMax parameter
    seed : int
        seed parameter
    nreal : int
        nreal parameter

    Returns
    -------
    mpds_geosClassicInput : (MPDS_GEOSCLASSICINPUT *)
        geosclassic input in C, intended for "GeosClassicSim" C program
    flag : bool
        indicates if the filling has succeeded (True) or failed (False)
    """
    # fname = 'fill_mpds_geosClassicInput'
    nxy = nx * ny
    nxyz = nxy * nz

    # Allocate mpds_geosClassicInput
    mpds_geosClassicInput = geosclassic.malloc_MPDS_GEOSCLASSICINPUT()

    # Init mpds_geosClassicInput
    geosclassic.MPDSGeosClassicInitGeosClassicInput(mpds_geosClassicInput)

    # mpds_geosClassicInput.consoleAppFlag
    mpds_geosClassicInput.consoleAppFlag = geosclassic.FALSE

    # mpds_geosClassicInput.simGrid
    mpds_geosClassicInput.simGrid = geosclassic.malloc_MPDS_GRID()

    mpds_geosClassicInput.simGrid.nx = int(nx)
    mpds_geosClassicInput.simGrid.ny = int(ny)
    mpds_geosClassicInput.simGrid.nz = int(nz)

    mpds_geosClassicInput.simGrid.sx = float(sx)
    mpds_geosClassicInput.simGrid.sy = float(sy)
    mpds_geosClassicInput.simGrid.sz = float(sz)

    mpds_geosClassicInput.simGrid.ox = float(ox)
    mpds_geosClassicInput.simGrid.oy = float(oy)
    mpds_geosClassicInput.simGrid.oz = float(oz)

    mpds_geosClassicInput.simGrid.nxy = nxy
    mpds_geosClassicInput.simGrid.nxyz = nxyz

    # mpds_geosClassicInput.varname
    geosclassic.mpds_allocate_and_set_geosClassicInput_varname(mpds_geosClassicInput, varname)

    # mpds_geosClassicInput.outputMode
    mpds_geosClassicInput.outputMode = geosclassic.GEOS_CLASSIC_OUTPUT_NO_FILE

    # mpds_geosClassicInput.outputReportFlag and mpds_geosClassicInput.outputReportFileName
    if outputReportFile is not None:
        mpds_geosClassicInput.outputReportFlag = geosclassic.TRUE
        geosclassic.mpds_allocate_and_set_geosClassicInput_outputReportFileName(mpds_geosClassicInput, outputReportFile)
    else:
        mpds_geosClassicInput.outputReportFlag = geosclassic.FALSE

    # mpds_geosClassicInput.computationMode
    mpds_geosClassicInput.computationMode = int(computationMode)

    # mpds_geosClassicInput.covModel
    if space_dim==1:
        cov_model_c, flag = covModel1D_py2C(cov_model, nx, ny, nz, sx, sy, sz, ox, oy, oz)
    elif space_dim==2:
        cov_model_c, flag = covModel2D_py2C(cov_model, nx, ny, nz, sx, sy, sz, ox, oy, oz)
    elif space_dim==3:
        cov_model_c, flag = covModel3D_py2C(cov_model, nx, ny, nz, sx, sy, sz, ox, oy, oz)

    if flag:
        mpds_geosClassicInput.covModel = cov_model_c
    else:
        return mpds_geosClassicInput, False

    # mpds_geosClassicInput.searchRadiusRelative
    mpds_geosClassicInput.searchRadiusRelative = float(searchRadiusRelative)

    # mpds_geosClassicInput.nneighborMax
    mpds_geosClassicInput.nneighborMax = int(nneighborMax)

    # mpds_geosClassicInput.searchNeighborhoodSortMode
    mpds_geosClassicInput.searchNeighborhoodSortMode = int(searchNeighborhoodSortMode)

    # mpds_geosClassicInput.ndataImage and mpds_geosClassicInput.dataImage
    if dataImage is None:
        mpds_geosClassicInput.ndataImage = 0
    else:
        dataImage = np.asarray(dataImage).reshape(-1)
        n = len(dataImage)
        mpds_geosClassicInput.ndataImage = n
        mpds_geosClassicInput.dataImage = geosclassic.new_MPDS_IMAGE_array(n)
        for i, dataIm in enumerate(dataImage):
            im_c = img_py2C(dataIm)
            geosclassic.MPDS_IMAGE_array_setitem(mpds_geosClassicInput.dataImage, i, im_c)
            geosclassic.free_MPDS_IMAGE(im_c)
            # geosclassic.MPDS_IMAGE_array_setitem(mpds_geosClassicInput.dataImage, i, img_py2C(dataIm))

    # mpds_geosClassicInput.ndataPointSet and mpds_geosClassicInput.dataPointSet
    if dataPointSet is None:
        mpds_geosClassicInput.ndataPointSet = 0
    else:
        dataPointSet = np.asarray(dataPointSet).reshape(-1)
        n = len(dataPointSet)
        mpds_geosClassicInput.ndataPointSet = n
        mpds_geosClassicInput.dataPointSet = geosclassic.new_MPDS_POINTSET_array(n)
        for i, dataPS in enumerate(dataPointSet):
            ps_c = ps_py2C(dataPS)
            geosclassic.MPDS_POINTSET_array_setitem(mpds_geosClassicInput.dataPointSet, i, ps_c)
            # geosclassic.free_MPDS_POINTSET(ps_c)
            #
            # geosclassic.MPDS_POINTSET_array_setitem(mpds_geosClassicInput.dataPointSet, i, ps_py2C(dataPS))

    # mpds_geosClassicInput.maskImageFlag and mpds_geosClassicInput.maskImage
    if mask is None:
        mpds_geosClassicInput.maskImageFlag = geosclassic.FALSE
    else:
        mpds_geosClassicInput.maskImageFlag = geosclassic.TRUE
        im = Img(nx=nx, ny=ny, nz=nz,
                 sx=sx, sy=sy, sz=sz,
                 ox=ox, oy=oy, oz=oz,
                 nv=1, val=mask)
        mpds_geosClassicInput.maskImage = img_py2C(im)

    # mpds_geosClassicInput.meanUsage, mpds_geosClassicInput.meanValue, mpds_geosClassicInput.meanImage
    if mean is None:
        mpds_geosClassicInput.meanUsage = 0
    elif mean.size == 1:
        mpds_geosClassicInput.meanUsage = 1
        mpds_geosClassicInput.meanValue = float(mean[0])
    elif mean.size == nxyz:
        mpds_geosClassicInput.meanUsage = 2
        im = Img(nx=nx, ny=ny, nz=nz,
                 sx=sx, sy=sy, sz=sz,
                 ox=ox, oy=oy, oz=oz,
                 nv=1, val=mean)
        mpds_geosClassicInput.meanImage = img_py2C(im)
    else:
        # print(f"ERROR ({fname}): can not integrate `mean` (not compatible with simulation grid)")
        return mpds_geosClassicInput, False

    # mpds_geosClassicInput.varianceUsage, mpds_geosClassicInput.varianceValue, mpds_geosClassicInput.varianceImage
    if var is None:
        mpds_geosClassicInput.varianceUsage = 0
    elif var.size == 1:
        mpds_geosClassicInput.varianceUsage = 1
        mpds_geosClassicInput.varianceValue = var[0]
    elif var.size == nxyz:
        mpds_geosClassicInput.varianceUsage = 2
        im = Img(nx=nx, ny=ny, nz=nz,
                 sx=sx, sy=sy, sz=sz,
                 ox=ox, oy=oy, oz=oz,
                 nv=1, val=var)
        mpds_geosClassicInput.varianceImage = img_py2C(im)
    else:
        # print(f"ERROR ({fname}): can not integrate `var` (not compatible with simulation grid)")
        return mpds_geosClassicInput, False

    # mpds_geosClassicInput.nGibbsSamplerPathMin
    mpds_geosClassicInput.nGibbsSamplerPathMin = int(nGibbsSamplerPathMin)

    # mpds_geosClassicInput.nGibbsSamplerPathMax
    mpds_geosClassicInput.nGibbsSamplerPathMax = int(nGibbsSamplerPathMax)

    # mpds_geosClassicInput.seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    mpds_geosClassicInput.seed = int(seed)

    # mpds_geosClassicInput.seedIncrement
    mpds_geosClassicInput.seedIncrement = 1

    # mpds_geosClassicInput.nrealization
    mpds_geosClassicInput.nrealization = int(nreal)

    return mpds_geosClassicInput, True
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulate1D(
        cov_model,
        dimension, spacing=1.0, origin=0.0,
        method='simple_kriging',
        nreal=1,
        mean=None, var=None,
        x=None, v=None,
        xIneqMin=None, vIneqMin=None,
        xIneqMax=None, vIneqMax=None,
        aggregate_data_op=None,
        aggregate_data_op_kwargs=None,
        aggregate_data_ineqMin_op='max',
        aggregate_data_ineqMin_op_kwargs=None,
        aggregate_data_ineqMax_op='min',
        aggregate_data_ineqMax_op_kwargs=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.0,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        nGibbsSamplerPathMin=50,
        nGibbsSamplerPathMax=200,
        seed=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Generates 1D simulations (Sequential Gaussian Simulation, SGS).

    A simulation takes place in (center of) grid cells, based on simple or
    ordinary kriging.

    Parameters
    ----------
    cov_model : :class:`geone.CovModel.CovModel1D`
        covariance model in 1D
    dimension : int
        `dimension=nx`, number of cells in the 1D simulation grid
    spacing : float, default: 1.0
        `spacing=sx`, cell size
    origin : float, default: 0.0
        `origin=ox`, origin of the 1D simulation grid (left border)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    nreal : int, default: 1
        number of realizations
    mean : function (callable), or array-like of floats, or float, optional
        kriging mean value:
        - if a function: function of one argument (xi) that returns the mean at
        location xi
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), mean values at grid cells (for
        non-stationary mean)
        - if a float: same mean value at every grid cell
        - by default (`None`): the mean of data value (`v`) (0.0 if no data) is
        considered at every grid cell
    var : function (callable), or array-like of floats, or float, optional
        kriging variance value:
        - if a function: function of one argument (xi) that returns the variance
        at location xi
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), variance values at grid cells (for
        non-stationary variance)
        - if a float: same variance value at every grid cell
        - by default (`None`): not used (use of covariance model only)
    x : 1D array-like of floats, optional
        data points locations (float coordinates); note: if one point, a float
        is accepted
    v : 1D array-like of floats, optional
        data values at `x` (`v[i]` is the data value at `x[i]`), array of same
        length as `x` (or float if one point)
    xIneqMin : 1D array-like of floats, optional
        data points locations (float coordinates), for inequality data with
        lower bound; note: if one point, a float is accepted
    vIneqMin : 1D array-like of floats, optional
        inequality data values, lower bounds, at `xIneqMin` (`vIneqMin[i]` is the
        data value at `xIneqMin[i]`), array of same length as `xIneqMin` (or
        float if one point)
    xIneqMax : 1D array-like of floats, optional
        data points locations (float coordinates), for inequality data with
        upper bound; note: if one point, a float is accepted
    vIneqMax : 1D array-like of floats, optional
        inequality data values, upper bounds, at `xIneqMax` (`vIneqMax[i]` is the
        data value at `xIneqMax[i]`), array of same length as `xIneqMax`  (or
        float if one point)
    aggregate_data_op : str {'sgs', 'krige', 'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, optional
        operation used to aggregate data points falling in the same grid cells;
        - if `aggregate_data_op='sgs'`: function `geone.covModel.sgs` is used
        with the covariance model `cov_model` given in arguments, as well as
        the parameter `nneighborMax` given in arguments unless it is given
        in `aggregate_data_op_kwargs`
        - if `aggregate_data_op='krige'`: function `geone.covModel.krige` is used
        with the covariance model `cov_model` given in arguments, as well as
        the parameters `use_unique_neighborhood`, `nneighborMax` given in
        arguments unless they are given in `aggregate_data_op_kwargs`
        - if `aggregate_data_op='most_freq'`: most frequent value is selected
        (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_op='random'`: value from a random point is selected
        - otherwise: the function `numpy.<aggregate_data_op>` is used with the
        additional parameters given by `aggregate_data_op_kwargs`, note that, e.g.
        `aggregate_data_op='quantile'` requires the additional parameter
        `q=<quantile_to_compute>`;
        note: if `aggregate_data_op='sgs'` or `aggregate_data_op='random'`, the
        aggregation is done for each realization (simulation), i.e. each simulation
        on the grid starts with a new set of values in conditioning grid cells;
        by default: if covariance model has stationary ranges and weight (sill),
        `aggregate_data_op='sgs'` is used, otherwise `aggregate_data_op='mean'`
    aggregate_data_op_kwargs : dict, optional
        keyword arguments to be passed to `geone.covModel.sgs`,
        `geone.covModel.krige`, or `numpy.<aggregate_data_op>`, according to
        the parameter `aggregate_data_op`
    aggregate_data_ineqMin_op : str {'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, default: 'max'
        operation used to aggregate inequality (min, lower boudns) data points
        falling in the same grid cells:
        - if `aggregate_data_ineqMin_op='most_freq'`: most frequent value is
        selected (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_ineqMin_op='random'`: value from a random point is
        selected
        - otherwise: the function `numpy.<aggregate_data_ineqMin_op>` is used with
        the additional parameters given by `aggregate_data_ineqMin_op_kwargs`,
        note that, e.g. `aggregate_data_ineqMin_op='quantile'` requires the
        additional parameter `q=<quantile_to_compute>`;
        note: in any case, the aggregation is done once, i.e. same inequality
        values are used for each simulation on the grid
    aggregate_data_ineqMin_op_kwargs : dict, optional
        keyword arguments to be passed to `numpy.<aggregate_data_ineqMin_op>`,
        according to the parameter `aggregate_data_ineqMin_op`
    aggregate_data_ineqMax_op : str {'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, default: 'min'
        operation used to aggregate inequality (min, lower boudns) data points
        falling in the same grid cells:
        - if `aggregate_data_ineqMax_op='most_freq'`: most frequent value is
        selected (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_ineqMax_op='random'`: value from a random point is
        selected
        - otherwise: the function `numpy.<aggregate_data_ineqMax_op>` is used with
        the additional parameters given by `aggregate_data_ineqMax_op_kwargs`,
        note that, e.g. `aggregate_data_ineqMax_op='quantile'` requires the
        additional parameter `q=<quantile_to_compute>`;
        note: in any case, the aggregation is done once, i.e. same inequality
        values are used for each simulation on the grid
    aggregate_data_ineqMax_op_kwargs : dict, optional
        keyword arguments to be passed to `numpy.<aggregate_data_ineqMax_op>`,
        according to the parameter `aggregate_data_ineqMax_op`
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    searchRadiusRelative : float, default: 1.0
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    nGibbsSamplerPathMin, nGibbsSamplerPathMax: ints, default: 50, 200
        minimal and maximal number of Gibbs sampler paths to deal with inequality
        data; the conditioning locations with inequality data are first simulated
        (based on truncated gaussian distribution) sequentially; then, these
        locations are re-simulated following a new path as many times as needed,
        but the total number of paths will be between `nGibbsSamplerPathMin` and
        `nGibbsSamplerPathMax`
    seed : int, optional
        seed for initializing random number generator
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=nreal` variables (simulations);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'simulate1D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = dimension, 1, 1
    sx, sy, sz = spacing, 1.0, 1.0
    ox, oy, oz = origin, 0.0, 0.0

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 1

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # nreal
    nreal = int(nreal) # cast to int if needed

    if nreal <= 0:
        if verbose >= 2:
            print(f'{fname}: nreal <= 0: nothing to do!')
        return None

    # cov_model
    if not isinstance(cov_model, gcm.CovModel1D):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model` is not valid")
        return None

    for el in cov_model.elem:
        # weight
        w = el[1]['w']
        if np.size(w) != 1 and np.size(w) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): `cov_model`: weight ('w') not compatible with simulation grid")
            return None
        # ranges
        if 'r' in el[1].keys():
            r  = el[1]['r']
            if np.size(r) != 1 and np.size(r) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): `cov_model`: range ('r') not compatible with simulation grid")
                return None
        # additional parameter (s)
        if 's' in el[1].keys():
            s  = el[1]['s']
            if np.size(s) != 1 and np.size(s) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): `cov_model`: parameter ('s') not compatible with simulation grid")
                return None

    # aggregate_data_op (default)
    if aggregate_data_op is None:
        if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
            aggregate_data_op = 'mean'
        else:
            aggregate_data_op = 'sgs'

    if aggregate_data_op_kwargs is None:
        aggregate_data_op_kwargs = {}

    if aggregate_data_ineqMin_op_kwargs is None:
        aggregate_data_ineqMin_op_kwargs = {}

    if aggregate_data_ineqMax_op_kwargs is None:
        aggregate_data_ineqMax_op_kwargs = {}

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 3
    elif method == 'ordinary_kriging':
        computationMode = 2
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # Check parameters - searchRadiusRelative
    if searchRadiusRelative < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchRadiusRelative` too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
        return None

    # Check parameters - nneighborMax
    if nneighborMax != -1 and nneighborMax <= 0:
        if verbose > 0:
            print(f"ERROR ({fname}): `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
        return None

    # Check parameters - searchNeighborhoodSortMode
    if searchNeighborhoodSortMode is None:
        # set greatest possible value
        if cov_model.is_stationary():
            searchNeighborhoodSortMode = 2
        else:
            searchNeighborhoodSortMode = 1
    else:
        if searchNeighborhoodSortMode == 2:
            if not cov_model.is_stationary():
                if verbose > 0:
                    print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                return None

    # if searchNeighborhoodSortMode is None:
    #     # set greatest possible value
    #     if cov_model.is_stationary():
    #         searchNeighborhoodSortMode = 2
    #     elif cov_model.is_orientation_stationary() and cov_model.is_range_stationary():
    #         searchNeighborhoodSortMode = 1
    #     else:
    #         searchNeighborhoodSortMode = 0
    # else:
    #     if searchNeighborhoodSortMode == 2:
    #         if not cov_model.is_stationary():
    #             if verbose > 0:
    #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
    #             return None
    #     elif searchNeighborhoodSortMode == 1:
    #         if not cov_model.is_orientation_stationary() or not cov_model.is_range_stationary():
    #             if verbose > 0:
    #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
    #             return None

    # Preparation of data points
    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 1) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

    if xIneqMin is not None:
        xIneqMin = np.asarray(xIneqMin, dtype='float').reshape(-1, 1) # cast in 2-dimensional array if needed
        vIneqMin = np.asarray(vIneqMin, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(vIneqMin) != xIneqMin.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `vIneqMin` is not valid")
            return None

    if xIneqMax is not None:
        xIneqMax = np.asarray(xIneqMax, dtype='float').reshape(-1, 1) # cast in 2-dimensional array if needed
        vIneqMax = np.asarray(vIneqMax, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(vIneqMax) != xIneqMax.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `vIneqMax` is not valid")
            return None

    # Check parameters - mean
    mean_x = mean
    if mean is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying `mean` not allowed with ordinary kriging")
        #     return None
        if callable(mean):
            if x is not None:
                mean_x = mean(x[:, 0])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            mean = mean(xi) # replace function 'mean' by its evaluation on the grid
        else:
            mean = np.asarray(mean, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if mean.size == 1:
                if x is not None:
                    mean_x = mean
            elif mean.size == nxyz:
                # mean = mean.reshape(nx)
                if x is not None:
                    mean_x = img.Img_interp_func(img.Img(nx, 1, 1, sx, 1., 1., ox, 0., 0., nv=1, val=mean), iy=0, iz=0)(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `mean` is not valid")
                return None

    # Check parameters - var
    var_x = var
    if var is not None:
        if method == 'ordinary_kriging':
            if verbose > 0:
                print(f"ERROR ({fname}): specifying `var` not allowed with ordinary kriging")
            return None
        if callable(var):
            if x is not None:
                var_x = var(x[:, 0])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            var = var(xi) # replace function 'var' by its evaluation on the grid
        else:
            var = np.asarray(var, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if var.size == 1:
                if x is not None:
                    var_x = var
            elif var.size == nxyz:
                # var = var.reshape(nx)
                if x is not None:
                    var_x = img.Img_interp_func(img.Img(nx, 1, 1, sx, 1., 1., ox, 0., 0., nv=1, val=var), iy=0, iz=0)(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `var` is not valid")
                return None

    # Prepare seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    seed = int(seed)

    # data points: x, v, xIneqMin, vIneqMin, xIneqMax, vIneqMax
    dataPointSet = []

    # data point set from x, v
    aggregate_data_by_simul = False
    if x is not None:
        if aggregate_data_op == 'krige' or aggregate_data_op == 'sgs':
            if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model with non-stationary weight or range cannot be used with `aggregate_data_op`='{aggregate_data_op}'")
                return None
            cov_model_agg = cov_model
            # Get grid cell with at least one data point:
            # x_agg: 2D array, each row contains the coordinates of the center of such cell
            im_tmp = img.imageFromPoints(x, values=None, varname=None,
                                         nx=nx, sx=sx, ox=ox,
                                         indicator_var=True, count_var=False)
            ind_agg = np.where(im_tmp.val[0])
            if len(ind_agg[0]) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None
            x_agg = im_tmp.xx()[ind_agg].reshape(-1, 1)
            # x_agg = im_tmp.xx()[*ind_agg].reshape(-1, 1) # ok from python 3.11 only ?
            ind_agg = ind_agg[2:] # remove index along z and y axes
            del(im_tmp)
            # Compute
            # - kriging estimate (v_agg) and kriging std (v_agg_std) at x_agg,
            # - or nreal simulation(s) (v_agg) at x_agg
            if mean is not None and mean.size > 1:
                mean_x_agg = mean[ind_agg]
                # mean_x_agg = mean[*ind_agg]
            else:
                mean_x_agg = mean
            if var is not None and var.size > 1:
                var_x_agg = var[ind_agg]
                # var_x_agg = var[*ind_agg]
            else:
                var_x_agg = var
            # Set parameters `nneighborMax` from the arguments if not given in `aggregate_data_op_kwargs`
            if 'nneighborMax' not in aggregate_data_op_kwargs.keys():
                aggregate_data_op_kwargs['nneighborMax'] = nneighborMax
            if aggregate_data_op == 'krige':
                try:
                    v_agg, v_agg_std = gcm.krige(x, v, x_agg, cov_model_agg, method=method,
                                                 mean_x=mean_x, mean_xu=mean_x_agg,
                                                 var_x=var_x, var_xu=var_x_agg,
                                                 verbose=0, **aggregate_data_op_kwargs)
                except:
                    if verbose > 0:
                        print(f"ERROR ({fname}): kriging error")
                    return None
            else:
                aggregate_data_by_simul = True
                v_agg = gcm.sgs(x, v, x_agg, cov_model_agg, method=method,
                                mean_x=mean_x, mean_xu=mean_x_agg,
                                var_x=var_x, var_xu=var_x_agg,
                                nreal=nreal, seed=seed,
                                verbose=0, **aggregate_data_op_kwargs)
                if v_agg is None:
                    if verbose > 0:
                        print(f"ERROR ({fname}): sgs error")
                    return None
            xx_agg = x_agg[:, 0]
            yy_agg = np.ones_like(xx_agg) * oy + 0.5 * sy
            zz_agg = np.ones_like(xx_agg) * oz + 0.5 * sz
        elif aggregate_data_op == 'random':
            aggregate_data_by_simul = True
            # Aggregate data on grid cell by taking random point
            xx = x[:, 0]
            yy = np.ones_like(xx) * oy + 0.5 * sy
            zz = np.ones_like(xx) * oz + 0.5 * sz
            # first realization of v_agg
            xx_agg, yy_agg, zz_agg, v_agg, i_inv = img.aggregateDataPointsWrtGrid(
                                                    xx, yy, zz, v,
                                                    nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                    op=aggregate_data_op, return_inverse=True,
                                                    **aggregate_data_op_kwargs)
            if len(xx_agg) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None
            # next realizations of v_agg
            v_agg = np.vstack((v_agg, np.zeros((nreal-1, v_agg.size))))
            for i in range(1, nreal):
                v_agg[i] = [v[np.random.choice(np.where(i_inv==j)[0])] for j in range(len(xx_agg))]
        else:
            # Aggregate data on grid cell by using the given operation
            xx = x[:, 0]
            yy = np.ones_like(xx) * oy + 0.5 * sy
            zz = np.ones_like(xx) * oz + 0.5 * sz
            try:
                xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                    xx, yy, zz, v,
                                                    nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                    op=aggregate_data_op, **aggregate_data_op_kwargs)
            except:
                if verbose > 0:
                    print(f"ERROR ({fname}): data aggregation (`aggregate_data_op='{aggregate_data_op}'`) failed")
                return None
            if len(xx_agg) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None

        if xIneqMin is not None or xIneqMax is not None:
            # Get single grid index for data points
            ix, iy, iz = img.pointToGridIndex(xx_agg, yy_agg, zz_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

        if not aggregate_data_by_simul:
            dataPointSet.append(
                PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
                )
        else:
            # Integrate data points from sgs index 0
            dataPointSet.append(
                PointSet(npt=v_agg.shape[1], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg[0])), varname=['X', 'Y', 'Z', varname])
                )

    # data point set from xIneqMin, vIneqMin
    if xIneqMin is not None:
        # Aggregate data on grid cell by using the given operation
        xx = xIneqMin[:, 0]
        yy = np.ones_like(xx) * oy + 0.5 * sy
        zz = np.ones_like(xx) * oz + 0.5 * sz
        try:
            xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg, v_ineqMin_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, vIneqMin,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op=aggregate_data_ineqMin_op, **aggregate_data_ineqMin_op_kwargs)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): inequality data (min) aggregation (`aggregate_data_op='{aggregate_data_ineqMin_op}'`) failed")
            return None
        if x is not None:
            # Get single grid index for inequality (min) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMin = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index with points from `x` and `xIneqMin`
            ig_inter, ig1, ig2 = np.intersect1d(ig, ig_ineqMin, assume_unique=True, return_indices=True)

            if ig_inter.size:
                if verbose > 1:
                    print(f'WARNING ({fname}): {ig_inter.size} grid cell(s) have both "inequality (min)" and "equality" data: inequlity data has been removed')
                    if not aggregate_data_by_simul:
                        ninconsistent = (v_agg[ig1] < v_ineqMin_agg[ig2]).sum()
                        if ninconsistent:
                            print(f'WARNING ({fname}): {ninconsistent} "inequality (min)" found')
                # Remove redundant points from inequality data set
                xx_ineqMin_agg = np.delete(xx_ineqMin_agg, ig2)
                yy_ineqMin_agg = np.delete(yy_ineqMin_agg, ig2)
                zz_ineqMin_agg = np.delete(zz_ineqMin_agg, ig2)
                v_ineqMin_agg = np.delete(v_ineqMin_agg, ig2)

        if v_ineqMin_agg.shape[0]:
            dataPointSet.append(
                PointSet(npt=v_ineqMin_agg.shape[0], nv=4, val=np.array((xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg, v_ineqMin_agg)), varname=['X', 'Y', 'Z', '{}_min'.format(varname)])
                )
        else:
            if verbose > 1:
                print(f"WARNING ({fname}): no inequality (min) data point in grid")
            xIneqMin = None

    # data point set from xIneqMax, vIneqMax
    if xIneqMax is not None:
        # Aggregate data on grid cell by using the given operation
        xx = xIneqMax[:, 0]
        yy = np.ones_like(xx) * oy + 0.5 * sy
        zz = np.ones_like(xx) * oz + 0.5 * sz
        try:
            xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg, v_ineqMax_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, vIneqMax,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op=aggregate_data_ineqMax_op, **aggregate_data_ineqMax_op_kwargs)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): inequality data (max) aggregation (`aggregate_data_op='{aggregate_data_ineqMax_op}'`) failed")
            return None
        if x is not None:
            # Get single grid index for inequality (max) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMax = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index with points from `x` and `xIneqMax`
            ig_inter, ig1, ig2 = np.intersect1d(ig, ig_ineqMax, assume_unique=True, return_indices=True)

            if ig_inter.size:
                if verbose > 1:
                    print(f'WARNING ({fname}): {ig_inter.size} grid cell(s) have both "inequality (max)" and "equality" data: inequlity data has been removed')
                    if not aggregate_data_by_simul:
                        ninconsistent = (v_agg[ig1] > v_ineqMax_agg[ig2]).sum()
                        if ninconsistent:
                            print(f'WARNING ({fname}): {ninconsistent} "inequality (max)" found')
                # Remove redundant points from inequality data set
                xx_ineqMax_agg = np.delete(xx_ineqMax_agg, ig2)
                yy_ineqMax_agg = np.delete(yy_ineqMax_agg, ig2)
                zz_ineqMax_agg = np.delete(zz_ineqMax_agg, ig2)
                v_ineqMax_agg = np.delete(v_ineqMax_agg, ig2)

        if xIneqMin is not None:
            # Get single grid index for inequality (min) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMin = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index for inequality (max) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMax = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index with points from `xIneqMin` and `xIneqMax`
            ig_inter, ig1, ig2 = np.intersect1d(ig_ineqMin, ig_ineqMax, assume_unique=True, return_indices=True)

            if ig_inter.size:
                ii = np.where(v_ineqMin_agg[ig1] > v_ineqMax_agg[ig2])[0]
                if len(ii):
                    if verbose > 0:
                        print(f'ERROR ({fname}): {len(ii)} grid cell(s) have inconsistent "inequality min" and "inequality max" data')
                    return None
                    # if verbose > 1:
                    #     print(f'WARNING ({fname}): {len(ii)} grid cell(s) have inconsistent "inequality min" and "inequality max" data: inequlity max data has been removed')
                    # ig2 = ig2[ii]
                    # # Remove inconsistent inequality max
                    # xx_ineqMax_agg = np.delete(xx_ineqMax_agg, ig2)
                    # yy_ineqMax_agg = np.delete(yy_ineqMax_agg, ig2)
                    # zz_ineqMax_agg = np.delete(zz_ineqMax_agg, ig2)
                    # v_ineqMax_agg = np.delete(v_ineqMax_agg, ig2)

        if v_ineqMax_agg.shape[0]:
            dataPointSet.append(
                PointSet(npt=v_ineqMax_agg.shape[0], nv=4, val=np.array((xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg, v_ineqMax_agg)), varname=['X', 'Y', 'Z', '{}_max'.format(varname)])
                )
        else:
            if verbose > 1:
                print(f"WARNING ({fname}): no inequality (max) data point in grid")
            xIneqMax = None

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if xIneqMin is not None:
            pts = np.vstack((pts, np.array((xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg)).T))
        if xIneqMax is not None:
            pts = np.vstack((pts, np.array((xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # Prepare seed (for simulation in grid)
    seed = seed + 986 # same increment (whatever the number or realization done in sgs above)

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if not aggregate_data_by_simul:
        # --- Fill mpds_geosClassicInput structure (C)
        mpds_geosClassicInput, flag = fill_mpds_geosClassicInput(
            space_dim,
            cov_model,
            nx, ny, nz,
            sx, sy, sz,
            ox, oy, oz,
            varname,
            outputReportFile,
            computationMode,
            None,
            dataPointSet,
            mask,
            mean,
            var,
            searchRadiusRelative,
            nneighborMax,
            searchNeighborhoodSortMode,
            nGibbsSamplerPathMin,
            nGibbsSamplerPathMax,
            seed,
            nreal)

        if not flag:
            if verbose > 0:
                print(f'ERROR ({fname}): can not fill input structure!')
            return None

        # --- Prepare mpds_geosClassicIOutput structure (C)
        # Allocate mpds_geosClassicOutput
        mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

        # Init mpds_geosClassicOutput
        geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

        # --- Set progress monitor
        mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
        geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

        # Set function to update progress monitor:
        # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
        # the function
        #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
        # should be used, but the following function can also be used:
        #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
        #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
        if verbose < 3:
            mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
        else:
            mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

        # # --- Set number of threads
        # if nthreads <= 0:
        #     nth = max(os.cpu_count() + nthreads, 1)
        # else:
        #     nth = nthreads

        if verbose >= 2:
            print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
            sys.stdout.flush()
            sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

        # --- Launch "GeosClassicSim" (launch C code)
        # err = geosclassic.MPDSGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
        err = geosclassic.MPDSOMPGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

        # Free memory on C side: mpds_geosClassicInput
        geosclassic.MPDSGeosClassicFreeGeosClassicInput(mpds_geosClassicInput)
        #geosclassic.MPDSFree(mpds_geosClassicInput)
        geosclassic.free_MPDS_GEOSCLASSICINPUT(mpds_geosClassicInput)

        if err:
            if verbose > 0:
                err_message = geosclassic.mpds_get_error_message(-err)
                err_message = err_message.replace('\n', '')
                print(err_message)
            geosclassic_output = None
        else:
            geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

        # Free memory on C side: mpds_geosClassicOutput
        geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
        #geosclassic.MPDSFree(mpds_geosClassicOutput)
        geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

        # Free memory on C side: mpds_progressMonitor
        #geosclassic.MPDSFree(mpds_progressMonitor)
        geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    else:
        # Equality data values will change for each realization
        if verbose >= 2:
            print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
            sys.stdout.flush()
            sys.stdout.flush() # twice!, so that the previous print is flushed before launching geos-classic...

        # Initialization of image and warnings for storing results
        image = Img(nx=nx, ny=ny, nz=nz, sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz, nv=nreal, val=np.nan)
        nwarning = 0
        warnings = []
        outputReportFile_ir = None # default
        for ir in range(nreal):
            if ir > 0:
                # Set equality data values for realization index ir
                dataPointSet[0].val[3] = v_agg[ir]

            if outputReportFile is not None:
                outputReportFile_ir = outputReportFile + f'.{ir}'

            # --- Fill mpds_geosClassicInput structure (C)
            mpds_geosClassicInput, flag = fill_mpds_geosClassicInput(
                space_dim,
                cov_model,
                nx, ny, nz,
                sx, sy, sz,
                ox, oy, oz,
                varname,
                outputReportFile_ir,
                computationMode,
                None,
                dataPointSet,
                mask,
                mean,
                var,
                searchRadiusRelative,
                nneighborMax,
                searchNeighborhoodSortMode,
                nGibbsSamplerPathMin,
                nGibbsSamplerPathMax,
                seed+ir, # seed for realization index ir
                1) # one real

            if not flag:
                if verbose > 0:
                    print(f'ERROR ({fname}): can not fill input structure!')
                return None

            # --- Prepare mpds_geosClassicIOutput structure (C)
            # Allocate mpds_geosClassicOutput
            mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

            # Init mpds_geosClassicOutput
            geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

            # --- Set progress monitor
            mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
            geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

            # Set function to update progress monitor:
            # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
            # the function
            #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
            # should be used, but the following function can also be used:
            #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
            #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
            mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
            # if verbose < 3:
            #     mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
            # else:
            #     mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
            #
            # if verbose >= 2:
            #     print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
            #     sys.stdout.flush()
            #     sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

            # --- Launch "GeosClassicSim" (launch C code)
            # err = geosclassic.MPDSGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
            err = geosclassic.MPDSOMPGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

            # Free memory on C side: mpds_geosClassicInput
            geosclassic.MPDSGeosClassicFreeGeosClassicInput(mpds_geosClassicInput)
            #geosclassic.MPDSFree(mpds_geosClassicInput)
            geosclassic.free_MPDS_GEOSCLASSICINPUT(mpds_geosClassicInput)

            if err:
                if verbose > 0:
                    err_message = geosclassic.mpds_get_error_message(-err)
                    err_message = err_message.replace('\n', '')
                    print(err_message)
                geosclassic_output = None
            else:
                geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

            # Free memory on C side: mpds_geosClassicOutput
            geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
            #geosclassic.MPDSFree(mpds_geosClassicOutput)
            geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

            # Free memory on C side: mpds_progressMonitor
            #geosclassic.MPDSFree(mpds_progressMonitor)
            geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

            if geosclassic_output is not None:
                image.val[ir] = geosclassic_output['image'].val[0]
                nwarning = nwarning + geosclassic_output['nwarning']
                warnings.extend(geosclassic_output['warnings'])

            del(geosclassic_output)

        # Remove duplicated warnings
        warnings = list(np.unique(warnings))

        # Rename variables
        ndigit = geosclassic.MPDS_GEOS_CLASSIC_NB_DIGIT_FOR_REALIZATION_NUMBER
        for j in range(image.nv):
            image.varname[j] = image.varname[j][:-ndigit] + f'{j:0{ndigit}d}'

        # Set geosclassic_output
        geosclassic_output = {'image':image, 'nwarning':nwarning, 'warnings':warnings}

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulate1D_mp(
        cov_model,
        dimension, spacing=1.0, origin=0.0,
        method='simple_kriging',
        nreal=1,
        mean=None, var=None,
        x=None, v=None,
        xIneqMin=None, vIneqMin=None,
        xIneqMax=None, vIneqMax=None,
        aggregate_data_op=None,
        aggregate_data_op_kwargs=None,
        aggregate_data_ineqMin_op='max',
        aggregate_data_ineqMin_op_kwargs=None,
        aggregate_data_ineqMax_op='min',
        aggregate_data_ineqMax_op_kwargs=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.0,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        nGibbsSamplerPathMin=50,
        nGibbsSamplerPathMax=200,
        seed=None,
        outputReportFile=None,
        treat_image_one_by_one=False,
        nproc=None, nthreads_per_proc=None,
        verbose=2):
    """
    Computes the same as the function `simulate1D`, using multiprocessing.

    All the parameters are the same as those of the function `simulate1D`,
    except `nthreads` that is replaced by the parameters `nproc` and
    `nthreads_per_proc`, and an extra parameter `treat_image_one_by_one`.

    This function launches multiple processes (based on `multiprocessing`
    package):
    - `nproc` parallel processes using each one `nthreads_per_proc` threads
    are launched [parallel calls of the function `simulate1D`];
    - the set of realizations (specified by `nreal`) is distributed in a
    balanced way over the processes;
    - in terms of resources, this implies the use of `nproc*nthreads_per_proc`
    cpu(s).

    Parameters
    ----------
    (new parameters)
    nproc : int, optional
        number of processes; by default (`None`):
        `nproc` is set to `min(nmax-1, nreal)` (but at least 1), where nmax is
        the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    nthreads_per_proc : int, optional
        number of thread(s) per process (should be > 0); by default (`None`):
        `nthreads_per_proc` is automatically computed as the maximal integer
        (but at least 1) such that `nproc*nthreads_per_proc <= nmax-1`, where
        nmax is the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    treat_image_one_by_one : bool, default: False
        keyword argument passed to the function `geone.img.gatherImages`:
        - if True: images (result of each process) are gathered one by one,
        i.e. the variables of each image are inserted in an output image one by
        one and removed from the source (slower, may save memory)
        - if False: images (result of each process) are gathered at once,
        i.e. the variables of all images are inserted in an output image at once,
        and then removed (faster)

    See function `simulate1D`.
    """
    # fname = 'simulate1D_mp'
    # Set number of processes: nproc
    if nproc is None:
        nproc = max(min(multiprocessing.cpu_count()-1, nreal), 1)
    else:
        nproc_tmp = nproc
        nproc = max(min(int(nproc), nreal), 1)
        if verbose > 0 and nproc != nproc_tmp:
            print('NOTE: number of processes has been changed (now: nproc={})'.format(nproc))

    # Set number of threads per process: nth
    if nthreads_per_proc is None:
        nth = max(int(np.floor((multiprocessing.cpu_count()-1) / nproc)), 1)
    else:
        nth = max(int(nthreads_per_proc), 1)
        if verbose > 0 and nth != nthreads_per_proc:
            print('NOTE: number of threads per process has been changed (now: nthreads_per_proc={})'.format(nth))

    if verbose > 0 and nproc * nth > multiprocessing.cpu_count():
        print('NOTE: total number of cpu(s) used will exceed number of cpu(s) of the system...')

    # Set the distribution of the realizations over the processes
    # Condider the Euclidean division of nreal by nproc:
    #     nreal = q * nproc + r, with 0 <= r < nproc
    # Then, (q+1) realizations will be done on process 0, 1, ..., r-1, and q realization on process r, ..., nproc-1
    # Define the list real_index_proc of length (nproc+1) such that
    #   real_index_proc[i], ..., real_index_proc[i+1] - 1 : are the realization indices run on process i
    q, r = np.divmod(nreal, nproc)
    real_index_proc = [i*q + min(i, r) for i in range(nproc+1)]

    if verbose >= 2:
        print('Geos-Classic running on {} process(es)... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(nproc, geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching geos-classic...

    # Prepare seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    seed = int(seed)

    outputReportFile_p = None

    # Set pool of nproc workers
    pool = multiprocessing.Pool(nproc)
    out_pool = []
    for i in range(nproc):
        # Adapt input for i-th process
        nreal_p = real_index_proc[i+1] - real_index_proc[i]
        seed_p = seed + real_index_proc[i]
        if outputReportFile is not None:
            outputReportFile_p = outputReportFile + f'.{i}'
        if i==0:
            verbose_p = min(verbose, 1) # allow to print error for process i
        else:
            verbose_p = 0
        # Launch geos-classic (i-th process)
        out_pool.append(
            pool.apply_async(simulate1D,
                args=(cov_model,
                dimension, spacing, origin,
                method,
                nreal_p,                     # nreal (adjusted)
                mean, var,
                x, v,
                xIneqMin, vIneqMin,
                xIneqMax, vIneqMax,
                aggregate_data_op,
                aggregate_data_op_kwargs,
                aggregate_data_ineqMin_op,
                aggregate_data_ineqMin_op_kwargs,
                aggregate_data_ineqMax_op,
                aggregate_data_ineqMax_op_kwargs,
                mask,
                add_data_point_to_mask,
                searchRadiusRelative,
                nneighborMax,
                searchNeighborhoodSortMode,
                nGibbsSamplerPathMin,
                nGibbsSamplerPathMax,
                seed_p,                      # seed (adjusted)
                outputReportFile_p,          # outputReportFile (adjusted)
                nth,                         # nthreads
                verbose_p)                   # verbose (adjusted)
                )
            )

    # Properly end working process
    pool.close() # Prevents any more tasks from being submitted to the pool,
    pool.join()  # then, wait for the worker processes to exit.

    # Get result from each process
    geosclassic_output_proc = [p.get() for p in out_pool]

    if np.any([out is None for out in geosclassic_output_proc]):
        return None

    # Gather results from every process
    # image
    image = []
    for out in geosclassic_output_proc:
        if out['image'] is not None:
            image.append(out['image'])
            del(out['image'])
    if len(image) == 0:
        image = None
    # Gather images and adjust variable names
    all_image = img.gatherImages(image, keep_varname=True, rem_var_from_source=True, treat_image_one_by_one=treat_image_one_by_one)
    ndigit = geosclassic.MPDS_GEOS_CLASSIC_NB_DIGIT_FOR_REALIZATION_NUMBER
    for j in range(all_image.nv):
        all_image.varname[j] = all_image.varname[j][:-ndigit] + f'{j:0{ndigit}d}'

    # nwarning
    nwarning = np.sum([out['nwarning'] for out in geosclassic_output_proc])
    # warnings
    warnings = list(np.unique(np.hstack([out['warnings'] for out in geosclassic_output_proc])))

    geosclassic_output = {'image':all_image, 'nwarning':nwarning, 'warnings':warnings}

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete (all process(es))')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulate2D(
        cov_model,
        dimension, spacing=(1.0, 1.0), origin=(0.0, 0.0),
        method='simple_kriging',
        nreal=1,
        mean=None, var=None,
        x=None, v=None,
        xIneqMin=None, vIneqMin=None,
        xIneqMax=None, vIneqMax=None,
        aggregate_data_op=None,
        aggregate_data_op_kwargs=None,
        aggregate_data_ineqMin_op='max',
        aggregate_data_ineqMin_op_kwargs=None,
        aggregate_data_ineqMax_op='min',
        aggregate_data_ineqMax_op_kwargs=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.0,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        nGibbsSamplerPathMin=50,
        nGibbsSamplerPathMax=200,
        seed=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Generates 2D simulations (Sequential Gaussian Simulation, SGS).

    A simulation takes place in (center of) grid cells, based on simple or
    ordinary kriging.

    Parameters
    ----------
    cov_model : :class:`geone.CovModel.CovModel2D`
        covariance model in 2D
    dimension : 2-tuple of ints
        `dimension=(nx, ny)`, number of cells in the 2D simulation grid along
        each axis
    spacing : 2-tuple of floats, default: (1.0, 1.0)
        `spacing=(sx, sy)`, cell size along each axis
    origin : 2-tuple of floats, default: (0.0, 0.0)
        `origin=(ox, oy)`, origin of the 2D simulation grid (lower-left corner)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    nreal : int, default: 1
        number of realizations
    mean : function (callable), or array-like of floats, or float, optional
        kriging mean value:
        - if a function: function of two arguments (xi, yi) that returns the mean
        at location (xi, yi)
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), mean values at grid cells (for
        non-stationary mean)
        - if a float: same mean value at every grid cell
        - by default (`None`): the mean of data value (`v`) (0.0 if no data) is
        considered at every grid cell
    var : function (callable), or array-like of floats, or float, optional
        kriging variance value:
        - if a function: function of two arguments (xi, yi) that returns the
        variance at location (xi, yi)
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), variance values at grid cells (for
        non-stationary variance)
        - if a float: same variance value at every grid cell
        - by default (`None`): not used (use of covariance model only)
    x : 2D array of floats of shape (n, 2), optional
        data points locations, with n the number of data points, each row of `x`
        is the float coordinates of one data point; note: if n=1, a 1D array of
        shape (2,) is accepted
    v : 1D array of floats of shape (n,), optional
        data values at `x` (`v[i]` is the data value at `x[i]`)
    xIneqMin : 2D array of floats of shape (nIneqMin, 2), optional
        data points locations, for inequality data with lower bound, with
        nIneqMin the number of data points, each row of `xIneqMin` is the float
        coordinates of one data point; note: if nIneqMin=1, a 1D array of
        shape (2,) is accepted
    vIneqMin : 1D array of floats of shape (nIneqMin,), optional
        inequality data values, lower bounds, at `xIneqMin` (`vIneqMin[i]` is the
        data value at `xIneqMin[i]`)
    xIneqMax : 2D array of floats of shape (nIneqMax, 2), optional
        data points locations, for inequality data with upper bound, with
        nIneqMax the number of data points, each row of `xIneqMax` is the float
        coordinates of one data point; note: if nIneqMax=1, a 1D array of
        shape (2,) is accepted
    vIneqMax : 1D array of floats of shape (nIneqMax,), optional
        inequality data values, upper bounds, at `xIneqMax` (`vIneqMax[i]` is the
        data value at `xIneqMax[i]`)
    aggregate_data_op : str {'sgs', 'krige', 'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, optional
        operation used to aggregate data points falling in the same grid cells;
        - if `aggregate_data_op='sgs'`: function `geone.covModel.sgs` is used
        with the covariance model `cov_model` given in arguments, as well as
        the parameter `nneighborMax` given in arguments unless it is given
        in `aggregate_data_op_kwargs`
        - if `aggregate_data_op='krige'`: function `geone.covModel.krige` is used
        with the covariance model `cov_model` given in arguments, as well as
        the parameters `use_unique_neighborhood`, `nneighborMax` given in
        arguments unless they are given in `aggregate_data_op_kwargs`
        - if `aggregate_data_op='most_freq'`: most frequent value is selected
        (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_op='random'`: value from a random point is selected
        - otherwise: the function `numpy.<aggregate_data_op>` is used with the
        additional parameters given by `aggregate_data_op_kwargs`, note that, e.g.
        `aggregate_data_op='quantile'` requires the additional parameter
        `q=<quantile_to_compute>`;
        note: if `aggregate_data_op='sgs'` or `aggregate_data_op='random'`, the
        aggregation is done for each realization (simulation), i.e. each simulation
        on the grid starts with a new set of values in conditioning grid cells;
        by default: if covariance model has stationary ranges and weight (sill),
        `aggregate_data_op='sgs'` is used, otherwise `aggregate_data_op='mean'`
    aggregate_data_op_kwargs : dict, optional
        keyword arguments to be passed to `geone.covModel.sgs`,
        `geone.covModel.krige`, or `numpy.<aggregate_data_op>`, according to
        the parameter `aggregate_data_op`
    aggregate_data_ineqMin_op : str {'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, default: 'max'
        operation used to aggregate inequality (min, lower boudns) data points
        falling in the same grid cells:
        - if `aggregate_data_ineqMin_op='most_freq'`: most frequent value is
        selected (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_ineqMin_op='random'`: value from a random point is
        selected
        - otherwise: the function `numpy.<aggregate_data_ineqMin_op>` is used with
        the additional parameters given by `aggregate_data_ineqMin_op_kwargs`,
        note that, e.g. `aggregate_data_ineqMin_op='quantile'` requires the
        additional parameter `q=<quantile_to_compute>`;
        note: in any case, the aggregation is done once, i.e. same inequality
        values are used for each simulation on the grid
    aggregate_data_ineqMin_op_kwargs : dict, optional
        keyword arguments to be passed to `numpy.<aggregate_data_ineqMin_op>`,
        according to the parameter `aggregate_data_ineqMin_op`
    aggregate_data_ineqMax_op : str {'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, default: 'min'
        operation used to aggregate inequality (min, lower boudns) data points
        falling in the same grid cells:
        - if `aggregate_data_ineqMax_op='most_freq'`: most frequent value is
        selected (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_ineqMax_op='random'`: value from a random point is
        selected
        - otherwise: the function `numpy.<aggregate_data_ineqMax_op>` is used with
        the additional parameters given by `aggregate_data_ineqMax_op_kwargs`,
        note that, e.g. `aggregate_data_ineqMax_op='quantile'` requires the
        additional parameter `q=<quantile_to_compute>`;
        note: in any case, the aggregation is done once, i.e. same inequality
        values are used for each simulation on the grid
    aggregate_data_ineqMax_op_kwargs : dict, optional
        keyword arguments to be passed to `numpy.<aggregate_data_ineqMax_op>`,
        according to the parameter `aggregate_data_ineqMax_op`
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    searchRadiusRelative : float, default: 1.0
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    nGibbsSamplerPathMin, nGibbsSamplerPathMax: ints, default: 50, 200
        minimal and maximal number of Gibbs sampler paths to deal with inequality
        data; the conditioning locations with inequality data are first simulated
        (based on truncated gaussian distribution) sequentially; then, these
        locations are re-simulated following a new path as many times as needed,
        but the total number of paths will be between `nGibbsSamplerPathMin` and
        `nGibbsSamplerPathMax`
    seed : int, optional
        seed for initializing random number generator
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=nreal` variables (simulations);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'simulate2D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = *dimension, 1
    sx, sy, sz = *spacing, 1.0
    ox, oy, oz = *origin, 0.0

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 2

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # nreal
    nreal = int(nreal) # cast to int if needed

    if nreal <= 0:
        if verbose >= 2:
            print(f'{fname}: nreal <= 0: nothing to do!')
        return None

    # cov_model
    if isinstance(cov_model, gcm.CovModel1D):
        cov_model = gcm.covModel1D_to_covModel2D(cov_model) # convert model 1D in 2D
            # -> will not be modified cov_model at exit

    if not isinstance(cov_model, gcm.CovModel2D):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model` is not valid")
        return None

    for el in cov_model.elem:
        # weight
        w = el[1]['w']
        if np.size(w) != 1 and np.size(w) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): `cov_model`: weight ('w') not compatible with simulation grid")
            return None
        # ranges
        if 'r' in el[1].keys():
            for r in el[1]['r']:
                if np.size(r) != 1 and np.size(r) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): `cov_model`: range ('r') not compatible with simulation grid")
                    return None
        # additional parameter (s)
        if 's' in el[1].keys():
            s  = el[1]['s']
            if np.size(s) != 1 and np.size(s) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): `cov_model`: parameter ('s') not compatible with simulation grid")
                return None

    # alpha
    angle = cov_model.alpha
    if np.size(angle) != 1 and np.size(angle) != nxyz:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model`: angle (alpha) not compatible with simulation grid")
        return None

    # aggregate_data_op (default)
    if aggregate_data_op is None:
        if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
            aggregate_data_op = 'mean'
        else:
            aggregate_data_op = 'sgs'

    if aggregate_data_op_kwargs is None:
        aggregate_data_op_kwargs = {}

    if aggregate_data_ineqMin_op_kwargs is None:
        aggregate_data_ineqMin_op_kwargs = {}

    if aggregate_data_ineqMax_op_kwargs is None:
        aggregate_data_ineqMax_op_kwargs = {}

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 3
    elif method == 'ordinary_kriging':
        computationMode = 2
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # Check parameters - searchRadiusRelative
    if searchRadiusRelative < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchRadiusRelative` too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
        return None

    # Check parameters - nneighborMax
    if nneighborMax != -1 and nneighborMax <= 0:
        if verbose > 0:
            print(f"ERROR ({fname}): `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
        return None

    # Check parameters - searchNeighborhoodSortMode
    if searchNeighborhoodSortMode is None:
        # set greatest possible value
        if cov_model.is_stationary():
            searchNeighborhoodSortMode = 2
        else:
            searchNeighborhoodSortMode = 1
    else:
        if searchNeighborhoodSortMode == 2:
            if not cov_model.is_stationary():
                if verbose > 0:
                    print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                return None

    # if searchNeighborhoodSortMode is None:
    #     # set greatest possible value
    #     if cov_model.is_stationary():
    #         searchNeighborhoodSortMode = 2
    #     elif cov_model.is_orientation_stationary() and cov_model.is_range_stationary():
    #         searchNeighborhoodSortMode = 1
    #     else:
    #         searchNeighborhoodSortMode = 0
    # else:
    #     if searchNeighborhoodSortMode == 2:
    #         if not cov_model.is_stationary():
    #             if verbose > 0:
    #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
    #             return None
    #     elif searchNeighborhoodSortMode == 1:
    #         if not cov_model.is_orientation_stationary() or not cov_model.is_range_stationary():
    #             if verbose > 0:
    #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
    #             return None

    # Preparation of data points
    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 2) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

    if xIneqMin is not None:
        xIneqMin = np.asarray(xIneqMin, dtype='float').reshape(-1, 2) # cast in 2-dimensional array if needed
        vIneqMin = np.asarray(vIneqMin, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(vIneqMin) != xIneqMin.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `vIneqMin` is not valid")
            return None

    if xIneqMax is not None:
        xIneqMax = np.asarray(xIneqMax, dtype='float').reshape(-1, 2) # cast in 2-dimensional array if needed
        vIneqMax = np.asarray(vIneqMax, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(vIneqMax) != xIneqMax.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `vIneqMax` is not valid")
            return None

    # Check parameters - mean
    mean_x = mean
    if mean is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying `mean` not allowed with ordinary kriging")
        #     return None
        if callable(mean):
            if x is not None:
                mean_x = mean(x[:, 0], x[:, 1])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            yi = oy + sy*(0.5+np.arange(ny)) # y-coordinate of cell center
            yyi, xxi = np.meshgrid(yi, xi, indexing='ij')
            mean = mean(xxi, yyi) # replace function 'mean' by its evaluation on the grid
        else:
            mean = np.asarray(mean, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if mean.size == 1:
                if x is not None:
                    mean_x = mean
            elif mean.size == nxyz:
                mean = mean.reshape(ny, nx)
                if x is not None:
                    mean_x = img.Img_interp_func(img.Img(nx, ny, 1, sx, sy, 1., ox, oy, 0., nv=1, val=mean), iz=0)(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `mean` is not valid")
                return None

    # Check parameters - var
    var_x = var
    if var is not None:
        if method == 'ordinary_kriging':
            if verbose > 0:
                print(f"ERROR ({fname}): specifying `var` not allowed with ordinary kriging")
            return None
        if callable(var):
            if x is not None:
                var_x = var(x[:, 0], x[:, 1])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            yi = oy + sy*(0.5+np.arange(ny)) # y-coordinate of cell center
            yyi, xxi = np.meshgrid(yi, xi, indexing='ij')
            var = var(xxi, yyi) # replace function 'var' by its evaluation on the grid
        else:
            var = np.asarray(var, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if var.size == 1:
                if x is not None:
                    var_x = var
            elif var.size == nxyz:
                var = var.reshape(ny, nx)
                if x is not None:
                    var_x = img.Img_interp_func(img.Img(nx, ny, 1, sx, sy, 1., ox, oy, 0., nv=1, val=var), iz=0)(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `var` is not valid")
                return None

    # Prepare seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    seed = int(seed)

    # data points: x, v, xIneqMin, vIneqMin, xIneqMax, vIneqMax
    dataPointSet = []

    # data point set from x, v
    aggregate_data_by_simul = False
    if x is not None:
        if aggregate_data_op == 'krige' or aggregate_data_op == 'sgs':
            if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model with non-stationary weight or range cannot be used with `aggregate_data_op`='{aggregate_data_op}'")
                return None
            if cov_model.is_orientation_stationary():
                cov_model_agg = cov_model
            else:
                cov_model_agg = gcm.copyCovModel(cov_model)
                cov_model_agg.set_alpha(0.0)
            # Get grid cell with at least one data point:
            # x_agg: 2D array, each row contains the coordinates of the center of such cell
            im_tmp = img.imageFromPoints(x, values=None, varname=None,
                                         nx=nx, ny=ny, sx=sx, sy=sy, ox=ox, oy=oy,
                                         indicator_var=True, count_var=False)
            ind_agg = np.where(im_tmp.val[0])
            if len(ind_agg[0]) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None
            x_agg = np.array((im_tmp.xx()[ind_agg].reshape(-1), im_tmp.yy()[ind_agg].reshape(-1))).T
            # x_agg = np.array((im_tmp.xx()[*ind_agg].reshape(-1), im_tmp.yy()[*ind_agg].reshape(-1))).T
            ind_agg = ind_agg[1:] # remove index along z axis
            del(im_tmp)
            # Compute
            # - kriging estimate (v_agg) and kriging std (v_agg_std) at x_agg,
            # - or nreal simulation(s) (v_agg) at x_agg
            if mean is not None and mean.size > 1:
                mean_x_agg = mean[ind_agg]
                # mean_x_agg = mean[*ind_agg]
            else:
                mean_x_agg = mean
            if var is not None and var.size > 1:
                var_x_agg = var[ind_agg]
                # var_x_agg = var[*ind_agg]
            else:
                var_x_agg = var
            if isinstance(cov_model.alpha, np.ndarray) and cov_model.alpha.size == nxyz:
                alpha_x_agg = cov_model.alpha.reshape(ny, nx)[ind_agg]
                # alpha_x_agg = cov_model.alpha.reshape(ny, nx)[*ind_agg]
            else:
                alpha_x_agg = cov_model.alpha
            # Set parameters `nneighborMax` from the arguments if not given in `aggregate_data_op_kwargs`
            if 'nneighborMax' not in aggregate_data_op_kwargs.keys():
                aggregate_data_op_kwargs['nneighborMax'] = nneighborMax
            if aggregate_data_op == 'krige':
                try:
                    v_agg, v_agg_std = gcm.krige(x, v, x_agg, cov_model_agg, method=method,
                                                 mean_x=mean_x, mean_xu=mean_x_agg,
                                                 var_x=var_x, var_xu=var_x_agg,
                                                 alpha_xu=alpha_x_agg,
                                                 verbose=0, **aggregate_data_op_kwargs)
                except:
                    if verbose > 0:
                        print(f"ERROR ({fname}): kriging error")
                    return None
            else:
                aggregate_data_by_simul = True
                v_agg = gcm.sgs(x, v, x_agg, cov_model_agg, method=method,
                                mean_x=mean_x, mean_xu=mean_x_agg,
                                var_x=var_x, var_xu=var_x_agg,
                                alpha_xu=alpha_x_agg,
                                nreal=nreal, seed=seed,
                                verbose=0, **aggregate_data_op_kwargs)
                if v_agg is None:
                    if verbose > 0:
                        print(f"ERROR ({fname}): sgs error")
                    return None
            xx_agg, yy_agg = x_agg.T
            zz_agg = np.ones_like(xx_agg) * oz + 0.5 * sz
        elif aggregate_data_op == 'random':
            aggregate_data_by_simul = True
            # Aggregate data on grid cell by taking random point
            xx, yy = x.T
            zz = np.ones_like(xx) * oz + 0.5 * sz
            # first realization of v_agg
            xx_agg, yy_agg, zz_agg, v_agg, i_inv = img.aggregateDataPointsWrtGrid(
                                                    xx, yy, zz, v,
                                                    nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                    op=aggregate_data_op, return_inverse=True,
                                                    **aggregate_data_op_kwargs)
            if len(xx_agg) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None
            # next realizations of v_agg
            v_agg = np.vstack((v_agg, np.zeros((nreal-1, v_agg.size))))
            for i in range(1, nreal):
                v_agg[i] = [v[np.random.choice(np.where(i_inv==j)[0])] for j in range(len(xx_agg))]
        else:
            # Aggregate data on grid cell by using the given operation
            xx, yy = x.T
            zz = np.ones_like(xx) * oz + 0.5 * sz
            try:
                xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                    xx, yy, zz, v,
                                                    nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                    op=aggregate_data_op, **aggregate_data_op_kwargs)
            except:
                if verbose > 0:
                    print(f"ERROR ({fname}): data aggregation (`aggregate_data_op='{aggregate_data_op}'`) failed")
                return None
            if len(xx_agg) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None

        if xIneqMin is not None or xIneqMax is not None:
            # Get single grid index for data points
            ix, iy, iz = img.pointToGridIndex(xx_agg, yy_agg, zz_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

        if not aggregate_data_by_simul:
            dataPointSet.append(
                PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
                )
        else:
            # Integrate data points from sgs index 0
            dataPointSet.append(
                PointSet(npt=v_agg.shape[1], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg[0])), varname=['X', 'Y', 'Z', varname])
                )

    # data point set from xIneqMin, vIneqMin
    if xIneqMin is not None:
        # Aggregate data on grid cell by using the given operation
        xx, yy = xIneqMin.T
        zz = np.ones_like(xx) * oz + 0.5 * sz
        try:
            xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg, v_ineqMin_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, vIneqMin,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op=aggregate_data_ineqMin_op, **aggregate_data_ineqMin_op_kwargs)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): inequality data (min) aggregation (`aggregate_data_op='{aggregate_data_ineqMin_op}'`) failed")
            return None
        if x is not None:
            # Get single grid index for inequality (min) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMin = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index with points from `x` and `xIneqMin`
            ig_inter, ig1, ig2 = np.intersect1d(ig, ig_ineqMin, assume_unique=True, return_indices=True)

            if ig_inter.size:
                if verbose > 1:
                    print(f'WARNING ({fname}): {ig_inter.size} grid cell(s) have both "inequality (min)" and "equality" data: inequlity data has been removed')
                    if not aggregate_data_by_simul:
                        ninconsistent = (v_agg[ig1] < v_ineqMin_agg[ig2]).sum()
                        if ninconsistent:
                            print(f'WARNING ({fname}): {ninconsistent} "inequality (min)" found')
                # Remove redundant points from inequality data set
                xx_ineqMin_agg = np.delete(xx_ineqMin_agg, ig2)
                yy_ineqMin_agg = np.delete(yy_ineqMin_agg, ig2)
                zz_ineqMin_agg = np.delete(zz_ineqMin_agg, ig2)
                v_ineqMin_agg = np.delete(v_ineqMin_agg, ig2)

        if v_ineqMin_agg.shape[0]:
            dataPointSet.append(
                PointSet(npt=v_ineqMin_agg.shape[0], nv=4, val=np.array((xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg, v_ineqMin_agg)), varname=['X', 'Y', 'Z', '{}_min'.format(varname)])
                )
        else:
            if verbose > 1:
                print(f"WARNING ({fname}): no inequality (min) data point in grid")
            xIneqMin = None

    # data point set from xIneqMax, vIneqMax
    if xIneqMax is not None:
        # Aggregate data on grid cell by using the given operation
        xx, yy = xIneqMax.T
        zz = np.ones_like(xx) * oz + 0.5 * sz
        try:
            xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg, v_ineqMax_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, vIneqMax,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op=aggregate_data_ineqMax_op, **aggregate_data_ineqMax_op_kwargs)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): inequality data (max) aggregation (`aggregate_data_op='{aggregate_data_ineqMax_op}'`) failed")
            return None
        if x is not None:
            # Get single grid index for inequality (max) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMax = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index with points from `x` and `xIneqMax`
            ig_inter, ig1, ig2 = np.intersect1d(ig, ig_ineqMax, assume_unique=True, return_indices=True)

            if ig_inter.size:
                if verbose > 1:
                    print(f'WARNING ({fname}): {ig_inter.size} grid cell(s) have both "inequality (max)" and "equality" data: inequlity data has been removed')
                    if not aggregate_data_by_simul:
                        ninconsistent = (v_agg[ig1] > v_ineqMax_agg[ig2]).sum()
                        if ninconsistent:
                            print(f'WARNING ({fname}): {ninconsistent} "inequality (max)" found')
                # Remove redundant points from inequality data set
                xx_ineqMax_agg = np.delete(xx_ineqMax_agg, ig2)
                yy_ineqMax_agg = np.delete(yy_ineqMax_agg, ig2)
                zz_ineqMax_agg = np.delete(zz_ineqMax_agg, ig2)
                v_ineqMax_agg = np.delete(v_ineqMax_agg, ig2)

        if xIneqMin is not None:
            # Get single grid index for inequality (min) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMin = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index for inequality (max) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMax = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index with points from `xIneqMin` and `xIneqMax`
            ig_inter, ig1, ig2 = np.intersect1d(ig_ineqMin, ig_ineqMax, assume_unique=True, return_indices=True)

            if ig_inter.size:
                ii = np.where(v_ineqMin_agg[ig1] > v_ineqMax_agg[ig2])[0]
                if len(ii):
                    if verbose > 0:
                        print(f'ERROR ({fname}): {len(ii)} grid cell(s) have inconsistent "inequality min" and "inequality max" data')
                    return None
                    # if verbose > 1:
                    #     print(f'WARNING ({fname}): {len(ii)} grid cell(s) have inconsistent "inequality min" and "inequality max" data: inequlity max data has been removed')
                    # ig2 = ig2[ii]
                    # # Remove inconsistent inequality max
                    # xx_ineqMax_agg = np.delete(xx_ineqMax_agg, ig2)
                    # yy_ineqMax_agg = np.delete(yy_ineqMax_agg, ig2)
                    # zz_ineqMax_agg = np.delete(zz_ineqMax_agg, ig2)
                    # v_ineqMax_agg = np.delete(v_ineqMax_agg, ig2)

        if v_ineqMax_agg.shape[0]:
            dataPointSet.append(
                PointSet(npt=v_ineqMax_agg.shape[0], nv=4, val=np.array((xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg, v_ineqMax_agg)), varname=['X', 'Y', 'Z', '{}_max'.format(varname)])
                )
        else:
            if verbose > 1:
                print(f"WARNING ({fname}): no inequality (max) data point in grid")
            xIneqMax = None

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if xIneqMin is not None:
            pts = np.vstack((pts, np.array((xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg)).T))
        if xIneqMax is not None:
            pts = np.vstack((pts, np.array((xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # Prepare seed (for simulation in grid)
    seed = seed + 986 # same increment (whatever the number or realization done in sgs above)

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if not aggregate_data_by_simul:
        # --- Fill mpds_geosClassicInput structure (C)
        mpds_geosClassicInput, flag = fill_mpds_geosClassicInput(
            space_dim,
            cov_model,
            nx, ny, nz,
            sx, sy, sz,
            ox, oy, oz,
            varname,
            outputReportFile,
            computationMode,
            None,
            dataPointSet,
            mask,
            mean,
            var,
            searchRadiusRelative,
            nneighborMax,
            searchNeighborhoodSortMode,
            nGibbsSamplerPathMin,
            nGibbsSamplerPathMax,
            seed,
            nreal)

        if not flag:
            if verbose > 0:
                print(f'ERROR ({fname}): can not fill input structure!')
            return None

        # --- Prepare mpds_geosClassicIOutput structure (C)
        # Allocate mpds_geosClassicOutput
        mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

        # Init mpds_geosClassicOutput
        geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

        # --- Set progress monitor
        mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
        geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

        # Set function to update progress monitor:
        # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
        # the function
        #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
        # should be used, but the following function can also be used:
        #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
        #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
        if verbose < 3:
            mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
        else:
            mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

        # # --- Set number of threads
        # if nthreads <= 0:
        #     nth = max(os.cpu_count() + nthreads, 1)
        # else:
        #     nth = nthreads

        if verbose >= 2:
            print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
            sys.stdout.flush()
            sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

        # --- Launch "GeosClassicSim" (launch C code)
        # err = geosclassic.MPDSGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
        err = geosclassic.MPDSOMPGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

        # Free memory on C side: mpds_geosClassicInput
        geosclassic.MPDSGeosClassicFreeGeosClassicInput(mpds_geosClassicInput)
        #geosclassic.MPDSFree(mpds_geosClassicInput)
        geosclassic.free_MPDS_GEOSCLASSICINPUT(mpds_geosClassicInput)

        if err:
            if verbose > 0:
                err_message = geosclassic.mpds_get_error_message(-err)
                err_message = err_message.replace('\n', '')
                print(err_message)
            geosclassic_output = None
        else:
            geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

        # Free memory on C side: mpds_geosClassicOutput
        geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
        #geosclassic.MPDSFree(mpds_geosClassicOutput)
        geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

        # Free memory on C side: mpds_progressMonitor
        #geosclassic.MPDSFree(mpds_progressMonitor)
        geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    else:
        # Equality data values will change for each realization
        if verbose >= 2:
            print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
            sys.stdout.flush()
            sys.stdout.flush() # twice!, so that the previous print is flushed before launching geos-classic...

        # Initialization of image and warnings for storing results
        image = Img(nx=nx, ny=ny, nz=nz, sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz, nv=nreal, val=np.nan)
        nwarning = 0
        warnings = []
        outputReportFile_ir = None # default
        for ir in range(nreal):
            if ir > 0:
                # Set equality data values for realization index ir
                dataPointSet[0].val[3] = v_agg[ir]

            if outputReportFile is not None:
                outputReportFile_ir = outputReportFile + f'.{ir}'

            # --- Fill mpds_geosClassicInput structure (C)
            mpds_geosClassicInput, flag = fill_mpds_geosClassicInput(
                space_dim,
                cov_model,
                nx, ny, nz,
                sx, sy, sz,
                ox, oy, oz,
                varname,
                outputReportFile_ir,
                computationMode,
                None,
                dataPointSet,
                mask,
                mean,
                var,
                searchRadiusRelative,
                nneighborMax,
                searchNeighborhoodSortMode,
                nGibbsSamplerPathMin,
                nGibbsSamplerPathMax,
                seed+ir, # seed for realization index ir
                1) # one real

            if not flag:
                if verbose > 0:
                    print(f'ERROR ({fname}): can not fill input structure!')
                return None

            # --- Prepare mpds_geosClassicIOutput structure (C)
            # Allocate mpds_geosClassicOutput
            mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

            # Init mpds_geosClassicOutput
            geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

            # --- Set progress monitor
            mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
            geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

            # Set function to update progress monitor:
            # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
            # the function
            #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
            # should be used, but the following function can also be used:
            #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
            #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
            mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
            # if verbose < 3:
            #     mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
            # else:
            #     mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
            #
            # if verbose >= 2:
            #     print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
            #     sys.stdout.flush()
            #     sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

            # --- Launch "GeosClassicSim" (launch C code)
            # err = geosclassic.MPDSGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
            err = geosclassic.MPDSOMPGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

            # Free memory on C side: mpds_geosClassicInput
            geosclassic.MPDSGeosClassicFreeGeosClassicInput(mpds_geosClassicInput)
            #geosclassic.MPDSFree(mpds_geosClassicInput)
            geosclassic.free_MPDS_GEOSCLASSICINPUT(mpds_geosClassicInput)

            if err:
                if verbose > 0:
                    err_message = geosclassic.mpds_get_error_message(-err)
                    err_message = err_message.replace('\n', '')
                    print(err_message)
                geosclassic_output = None
            else:
                geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

            # Free memory on C side: mpds_geosClassicOutput
            geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
            #geosclassic.MPDSFree(mpds_geosClassicOutput)
            geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

            # Free memory on C side: mpds_progressMonitor
            #geosclassic.MPDSFree(mpds_progressMonitor)
            geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

            if geosclassic_output is not None:
                image.val[ir] = geosclassic_output['image'].val[0]
                nwarning = nwarning + geosclassic_output['nwarning']
                warnings.extend(geosclassic_output['warnings'])

            del(geosclassic_output)

        # Remove duplicated warnings
        warnings = list(np.unique(warnings))

        # Rename variables
        ndigit = geosclassic.MPDS_GEOS_CLASSIC_NB_DIGIT_FOR_REALIZATION_NUMBER
        for j in range(image.nv):
            image.varname[j] = image.varname[j][:-ndigit] + f'{j:0{ndigit}d}'

        # Set geosclassic_output
        geosclassic_output = {'image':image, 'nwarning':nwarning, 'warnings':warnings}

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulate2D_mp(
        cov_model,
        dimension, spacing=(1.0, 1.0), origin=(0.0, 0.0),
        method='simple_kriging',
        nreal=1,
        mean=None, var=None,
        x=None, v=None,
        xIneqMin=None, vIneqMin=None,
        xIneqMax=None, vIneqMax=None,
        aggregate_data_op=None,
        aggregate_data_op_kwargs=None,
        aggregate_data_ineqMin_op='max',
        aggregate_data_ineqMin_op_kwargs=None,
        aggregate_data_ineqMax_op='min',
        aggregate_data_ineqMax_op_kwargs=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.0,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        nGibbsSamplerPathMin=50,
        nGibbsSamplerPathMax=200,
        seed=None,
        outputReportFile=None,
        treat_image_one_by_one=False,
        nproc=None, nthreads_per_proc=None,
        verbose=2):
    """
    Computes the same as the function `simulate2D`, using multiprocessing.

    All the parameters are the same as those of the function `simulate2D`,
    except `nthreads` that is replaced by the parameters `nproc` and
    `nthreads_per_proc`, and an extra parameter `treat_image_one_by_one`.

    This function launches multiple processes (based on `multiprocessing`
    package):
    - `nproc` parallel processes using each one `nthreads_per_proc` threads
    are launched [parallel calls of the function `simulate2D`];
    - the set of realizations (specified by `nreal`) is distributed in a
    balanced way over the processes;
    - in terms of resources, this implies the use of `nproc*nthreads_per_proc`
    cpu(s).

    Parameters
    ----------
    (new parameters)
    nproc : int, optional
        number of processes; by default (`None`):
        `nproc` is set to `min(nmax-1, nreal)` (but at least 1), where nmax is
        the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    nthreads_per_proc : int, optional
        number of thread(s) per process (should be > 0); by default (`None`):
        `nthreads_per_proc` is automatically computed as the maximal integer
        (but at least 1) such that `nproc*nthreads_per_proc <= nmax-1`, where
        nmax is the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    treat_image_one_by_one : bool, default: False
        keyword argument passed to the function `geone.img.gatherImages`:
        - if True: images (result of each process) are gathered one by one,
        i.e. the variables of each image are inserted in an output image one by
        one and removed from the source (slower, may save memory)
        - if False: images (result of each process) are gathered at once,
        i.e. the variables of all images are inserted in an output image at once,
        and then removed (faster)

    See function `simulate2D`.
    """
    # fname = 'simulate2D_mp'

    # Set number of processes: nproc
    if nproc is None:
        nproc = max(min(multiprocessing.cpu_count()-1, nreal), 1)
    else:
        nproc_tmp = nproc
        nproc = max(min(int(nproc), nreal), 1)
        if verbose > 0 and nproc != nproc_tmp:
            print('NOTE: number of processes has been changed (now: nproc={})'.format(nproc))

    # Set number of threads per process: nth
    if nthreads_per_proc is None:
        nth = max(int(np.floor((multiprocessing.cpu_count()-1) / nproc)), 1)
    else:
        nth = max(int(nthreads_per_proc), 1)
        if verbose > 0 and nth != nthreads_per_proc:
            print('NOTE: number of threads per process has been changed (now: nthreads_per_proc={})'.format(nth))

    if verbose > 0 and nproc * nth > multiprocessing.cpu_count():
        print('NOTE: total number of cpu(s) used will exceed number of cpu(s) of the system...')

    # Set the distribution of the realizations over the processes
    # Condider the Euclidean division of nreal by nproc:
    #     nreal = q * nproc + r, with 0 <= r < nproc
    # Then, (q+1) realizations will be done on process 0, 1, ..., r-1, and q realization on process r, ..., nproc-1
    # Define the list real_index_proc of length (nproc+1) such that
    #   real_index_proc[i], ..., real_index_proc[i+1] - 1 : are the realization indices run on process i
    q, r = np.divmod(nreal, nproc)
    real_index_proc = [i*q + min(i, r) for i in range(nproc+1)]

    if verbose >= 2:
        print('Geos-Classic running on {} process(es)... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(nproc, geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching geos-classic...

    # Prepare seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    seed = int(seed)

    outputReportFile_p = None

    # Set pool of nproc workers
    pool = multiprocessing.Pool(nproc)
    out_pool = []
    for i in range(nproc):
        # Adapt input for i-th process
        nreal_p = real_index_proc[i+1] - real_index_proc[i]
        seed_p = seed + real_index_proc[i]
        if outputReportFile is not None:
            outputReportFile_p = outputReportFile + f'.{i}'
        if i==0:
            verbose_p = min(verbose, 1) # allow to print error for process i
        else:
            verbose_p = 0
        # Launch geos-classic (i-th process)
        out_pool.append(
            pool.apply_async(simulate2D,
                args=(cov_model,
                dimension, spacing, origin,
                method,
                nreal_p,                     # nreal (adjusted)
                mean, var,
                x, v,
                xIneqMin, vIneqMin,
                xIneqMax, vIneqMax,
                aggregate_data_op,
                aggregate_data_op_kwargs,
                aggregate_data_ineqMin_op,
                aggregate_data_ineqMin_op_kwargs,
                aggregate_data_ineqMax_op,
                aggregate_data_ineqMax_op_kwargs,
                mask,
                add_data_point_to_mask,
                searchRadiusRelative,
                nneighborMax,
                searchNeighborhoodSortMode,
                nGibbsSamplerPathMin,
                nGibbsSamplerPathMax,
                seed_p,                      # seed (adjusted)
                outputReportFile_p,          # outputReportFile (adjusted)
                nth,                         # nthreads
                verbose_p)                   # verbose (adjusted)
                )
            )

    # Properly end working process
    pool.close() # Prevents any more tasks from being submitted to the pool,
    pool.join()  # then, wait for the worker processes to exit.

    # Get result from each process
    geosclassic_output_proc = [p.get() for p in out_pool]

    if np.any([out is None for out in geosclassic_output_proc]):
        return None

    # Gather results from every process
    # image
    image = []
    for out in geosclassic_output_proc:
        if out['image'] is not None:
            image.append(out['image'])
            del(out['image'])
    if len(image) == 0:
        image = None
    # Gather images and adjust variable names
    all_image = img.gatherImages(image, keep_varname=True, rem_var_from_source=True, treat_image_one_by_one=treat_image_one_by_one)
    ndigit = geosclassic.MPDS_GEOS_CLASSIC_NB_DIGIT_FOR_REALIZATION_NUMBER
    for j in range(all_image.nv):
        all_image.varname[j] = all_image.varname[j][:-ndigit] + f'{j:0{ndigit}d}'

    # nwarning
    nwarning = np.sum([out['nwarning'] for out in geosclassic_output_proc])
    # warnings
    warnings = list(np.unique(np.hstack([out['warnings'] for out in geosclassic_output_proc])))

    geosclassic_output = {'image':all_image, 'nwarning':nwarning, 'warnings':warnings}

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete (all process(es))')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulate3D(
        cov_model,
        dimension, spacing=(1.0, 1.0, 1.0), origin=(0.0, 0.0, 0.0),
        method='simple_kriging',
        nreal=1,
        mean=None, var=None,
        x=None, v=None,
        xIneqMin=None, vIneqMin=None,
        xIneqMax=None, vIneqMax=None,
        aggregate_data_op=None,
        aggregate_data_op_kwargs=None,
        aggregate_data_ineqMin_op='max',
        aggregate_data_ineqMin_op_kwargs=None,
        aggregate_data_ineqMax_op='min',
        aggregate_data_ineqMax_op_kwargs=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.0,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        nGibbsSamplerPathMin=50,
        nGibbsSamplerPathMax=200,
        seed=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Generates 3D simulations (Sequential Gaussian Simulation, SGS).

    A simulation takes place in (center of) grid cells, based on simple or
    ordinary kriging.

    Parameters
    ----------
    cov_model : :class:`geone.CovModel.CovModel3D`
        covariance model in 3D
    dimension : 3-tuple of ints
        `dimension=(nx, ny, nz)`, number of cells in the 3D simulation grid along
        each axis
    spacing : 3-tuple of floats, default: (1.0,1.0, 1.0)
        `spacing=(sx, sy, sz)`, cell size along each axis
    origin : 3-tuple of floats, default: (0.0, 0.0, 0.0)
        `origin=(ox, oy, oz)`, origin of the 3D simulation grid (bottom-lower-left
        corner)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    nreal : int, default: 1
        number of realizations
    mean : function (callable), or array-like of floats, or float, optional
        kriging mean value:
        - if a function: function of three arguments (xi, yi, zi) that returns
        the mean at location (xi, yi, zi)
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), mean values at grid cells (for
        non-stationary mean)
        - if a float: same mean value at every grid cell
        - by default (`None`): the mean of data value (`v`) (0.0 if no data) is
        considered at every grid cell
    var : function (callable), or array-like of floats, or float, optional
        kriging variance value:
        - if a function: function of three arguments (xi, yi, yi) that returns
        the variance at location (xi, yi, zi)
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), variance values at grid cells (for
        non-stationary variance)
        - if a float: same variance value at every grid cell
        - by default (`None`): not used (use of covariance model only)
    x : 2D array of floats of shape (n, 3), optional
        data points locations, with n the number of data points, each row of `x`
        is the float coordinates of one data point; note: if n=1, a 1D array of
        shape (3,) is accepted
    v : 1D array of floats of shape (n,), optional
        data values at `x` (`v[i]` is the data value at `x[i]`)
    xIneqMin : 2D array of floats of shape (nIneqMin, 3), optional
        data points locations, for inequality data with lower bound, with
        nIneqMin the number of data points, each row of `xIneqMin` is the float
        coordinates of one data point; note: if nIneqMin=1, a 1D array of
        shape (3,) is accepted
    vIneqMin : 1D array of floats of shape (nIneqMin,), optional
        inequality data values, lower bounds, at `xIneqMin` (`vIneqMin[i]` is the
        data value at `xIneqMin[i]`)
    xIneqMax : 2D array of floats of shape (nIneqMax, 3), optional
        data points locations, for inequality data with upper bound, with
        nIneqMax the number of data points, each row of `xIneqMax` is the float
        coordinates of one data point; note: if nIneqMax=1, a 1D array of
        shape (3,) is accepted
    vIneqMax : 1D array of floats of shape (nIneqMax,), optional
        inequality data values, upper bounds, at `xIneqMax` (`vIneqMax[i]` is the
        data value at `xIneqMax[i]`)
    aggregate_data_op : str {'sgs', 'krige', 'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, optional
        operation used to aggregate data points falling in the same grid cells;
        - if `aggregate_data_op='sgs'`: function `geone.covModel.sgs` is used
        with the covariance model `cov_model` given in arguments, as well as
        the parameter `nneighborMax` given in arguments unless it is given
        in `aggregate_data_op_kwargs`
        - if `aggregate_data_op='krige'`: function `geone.covModel.krige` is used
        with the covariance model `cov_model` given in arguments, as well as
        the parameters `use_unique_neighborhood`, `nneighborMax` given in
        arguments unless they are given in `aggregate_data_op_kwargs`
        - if `aggregate_data_op='most_freq'`: most frequent value is selected
        (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_op='random'`: value from a random point is selected
        - otherwise: the function `numpy.<aggregate_data_op>` is used with the
        additional parameters given by `aggregate_data_op_kwargs`, note that, e.g.
        `aggregate_data_op='quantile'` requires the additional parameter
        `q=<quantile_to_compute>`;
        note: if `aggregate_data_op='sgs'` or `aggregate_data_op='random'`, the
        aggregation is done for each realization (simulation), i.e. each simulation
        on the grid starts with a new set of values in conditioning grid cells;
        by default: if covariance model has stationary ranges and weight (sill),
        `aggregate_data_op='sgs'` is used, otherwise `aggregate_data_op='mean'`
    aggregate_data_op_kwargs : dict, optional
        keyword arguments to be passed to `geone.covModel.sgs`,
        `geone.covModel.krige`, or `numpy.<aggregate_data_op>`, according to
        the parameter `aggregate_data_op`
    aggregate_data_ineqMin_op : str {'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, default: 'max'
        operation used to aggregate inequality (min, lower boudns) data points
        falling in the same grid cells:
        - if `aggregate_data_ineqMin_op='most_freq'`: most frequent value is
        selected (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_ineqMin_op='random'`: value from a random point is
        selected
        - otherwise: the function `numpy.<aggregate_data_ineqMin_op>` is used with
        the additional parameters given by `aggregate_data_ineqMin_op_kwargs`,
        note that, e.g. `aggregate_data_ineqMin_op='quantile'` requires the
        additional parameter `q=<quantile_to_compute>`;
        note: in any case, the aggregation is done once, i.e. same inequality
        values are used for each simulation on the grid
    aggregate_data_ineqMin_op_kwargs : dict, optional
        keyword arguments to be passed to `numpy.<aggregate_data_ineqMin_op>`,
        according to the parameter `aggregate_data_ineqMin_op`
    aggregate_data_ineqMax_op : str {'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, default: 'min'
        operation used to aggregate inequality (min, lower boudns) data points
        falling in the same grid cells:
        - if `aggregate_data_ineqMax_op='most_freq'`: most frequent value is
        selected (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_ineqMax_op='random'`: value from a random point is
        selected
        - otherwise: the function `numpy.<aggregate_data_ineqMax_op>` is used with
        the additional parameters given by `aggregate_data_ineqMax_op_kwargs`,
        note that, e.g. `aggregate_data_ineqMax_op='quantile'` requires the
        additional parameter `q=<quantile_to_compute>`;
        note: in any case, the aggregation is done once, i.e. same inequality
        values are used for each simulation on the grid
    aggregate_data_ineqMax_op_kwargs : dict, optional
        keyword arguments to be passed to `numpy.<aggregate_data_ineqMax_op>`,
        according to the parameter `aggregate_data_ineqMax_op`
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    searchRadiusRelative : float, default: 1.0
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    nGibbsSamplerPathMin, nGibbsSamplerPathMax: ints, default: 50, 200
        minimal and maximal number of Gibbs sampler paths to deal with inequality
        data; the conditioning locations with inequality data are first simulated
        (based on truncated gaussian distribution) sequentially; then, these
        locations are re-simulated following a new path as many times as needed,
        but the total number of paths will be between `nGibbsSamplerPathMin` and
        `nGibbsSamplerPathMax`
    seed : int, optional
        seed for initializing random number generator
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=nreal` variables (simulations);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'simulate3D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = dimension
    sx, sy, sz = spacing
    ox, oy, oz = origin

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 3

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # nreal
    nreal = int(nreal) # cast to int if needed

    if nreal <= 0:
        if verbose >= 2:
            print(f'{fname}: nreal <= 0: nothing to do!')
        return None

    # cov_model
    if isinstance(cov_model, gcm.CovModel1D):
        cov_model = gcm.covModel1D_to_covModel3D(cov_model) # convert model 1D in 3D
            # -> will not be modified cov_model at exit

    if not isinstance(cov_model, gcm.CovModel3D):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model` is not valid")
        return None

    for el in cov_model.elem:
        # weight
        w = el[1]['w']
        if np.size(w) != 1 and np.size(w) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): `cov_model`: weight ('w') not compatible with simulation grid")
            return None
        # ranges
        if 'r' in el[1].keys():
            for r in el[1]['r']:
                if np.size(r) != 1 and np.size(r) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): `cov_model`: range ('r') not compatible with simulation grid")
                    return None
        # additional parameter (s)
        if 's' in el[1].keys():
            s  = el[1]['s']
            if np.size(s) != 1 and np.size(s) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): `cov_model`: parameter ('s') not compatible with simulation grid")
                return None

    # alpha
    angle = cov_model.alpha
    if np.size(angle) != 1 and np.size(angle) != nxyz:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model`: angle (alpha) not compatible with simulation grid")
        return None

    # beta
    angle = cov_model.beta
    if np.size(angle) != 1 and np.size(angle) != nxyz:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model`: angle (beta) not compatible with simulation grid")
        return None

    # gamma
    angle = cov_model.gamma
    if np.size(angle) != 1 and np.size(angle) != nxyz:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model`: angle (gamma) not compatible with simulation grid")
        return None

    # aggregate_data_op (default)
    if aggregate_data_op is None:
        if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
            aggregate_data_op = 'mean'
        else:
            aggregate_data_op = 'sgs'

    if aggregate_data_op_kwargs is None:
        aggregate_data_op_kwargs = {}

    if aggregate_data_ineqMin_op_kwargs is None:
        aggregate_data_ineqMin_op_kwargs = {}

    if aggregate_data_ineqMax_op_kwargs is None:
        aggregate_data_ineqMax_op_kwargs = {}

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 3
    elif method == 'ordinary_kriging':
        computationMode = 2
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # Check parameters - searchRadiusRelative
    if searchRadiusRelative < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchRadiusRelative` too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
        return None

    # Check parameters - nneighborMax
    if nneighborMax != -1 and nneighborMax <= 0:
        if verbose > 0:
            print(f"ERROR ({fname}): `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
        return None

    # Check parameters - searchNeighborhoodSortMode
    if searchNeighborhoodSortMode is None:
        # set greatest possible value
        if cov_model.is_stationary():
            searchNeighborhoodSortMode = 2
        else:
            searchNeighborhoodSortMode = 1
    else:
        if searchNeighborhoodSortMode == 2:
            if not cov_model.is_stationary():
                if verbose > 0:
                    print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                return None

    # if searchNeighborhoodSortMode is None:
    #     # set greatest possible value
    #     if cov_model.is_stationary():
    #         searchNeighborhoodSortMode = 2
    #     elif cov_model.is_orientation_stationary() and cov_model.is_range_stationary():
    #         searchNeighborhoodSortMode = 1
    #     else:
    #         searchNeighborhoodSortMode = 0
    # else:
    #     if searchNeighborhoodSortMode == 2:
    #         if not cov_model.is_stationary():
    #             if verbose > 0:
    #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
    #             return None
    #     elif searchNeighborhoodSortMode == 1:
    #         if not cov_model.is_orientation_stationary() or not cov_model.is_range_stationary():
    #             if verbose > 0:
    #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
    #             return None

    # Preparation of data points
    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 3) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

    if xIneqMin is not None:
        xIneqMin = np.asarray(xIneqMin, dtype='float').reshape(-1, 3) # cast in 2-dimensional array if needed
        vIneqMin = np.asarray(vIneqMin, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(vIneqMin) != xIneqMin.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `vIneqMin` is not valid")
            return None

    if xIneqMax is not None:
        xIneqMax = np.asarray(xIneqMax, dtype='float').reshape(-1, 3) # cast in 2-dimensional array if needed
        vIneqMax = np.asarray(vIneqMax, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(vIneqMax) != xIneqMax.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `vIneqMax` is not valid")
            return None

    # Check parameters - mean
    mean_x = mean
    if mean is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying `mean` not allowed with ordinary kriging")
        #     return None
        if callable(mean):
            if x is not None:
                mean_x = mean(x[:, 0], x[:, 1], x[:, 2])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            yi = oy + sy*(0.5+np.arange(ny)) # y-coordinate of cell center
            zi = oz + sz*(0.5+np.arange(nz)) # z-coordinate of cell center
            zzi, yyi, xxi = np.meshgrid(zi, yi, xi, indexing='ij')
            mean = mean(xxi, yyi, zzi) # replace function 'mean' by its evaluation on the grid
        else:
            mean = np.asarray(mean, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if mean.size == 1:
                if x is not None:
                    mean_x = mean
            elif mean.size == nxyz:
                mean = mean.reshape(nz, ny, nx)
                if x is not None:
                    mean_x = img.Img_interp_func(img.Img(nx, ny, nz, sx, sy, sz, ox, oy, oz, nv=1, val=mean))(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `mean` is not valid")
                return None

    # Check parameters - var
    var_x = var
    if var is not None:
        if method == 'ordinary_kriging':
            if verbose > 0:
                print(f"ERROR ({fname}): specifying `var` not allowed with ordinary kriging")
            return None
        if callable(var):
            if x is not None:
                var_x = var(x[:, 0], x[:, 1], x[:, 2])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            yi = oy + sy*(0.5+np.arange(ny)) # y-coordinate of cell center
            zi = oz + sz*(0.5+np.arange(nz)) # z-coordinate of cell center
            zzi, yyi, xxi = np.meshgrid(zi, yi, xi, indexing='ij')
            var = var(xxi, yyi, zzi) # replace function 'var' by its evaluation on the grid
        else:
            var = np.asarray(var, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if var.size == 1:
                if x is not None:
                    var_x = var
            elif var.size == nxyz:
                var = var.reshape(nz, ny, nx)
                if x is not None:
                    var_x = img.Img_interp_func(img.Img(nx, ny, nz, sx, sy, sz, ox, oy, oz, nv=1, val=var))(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `var` is not valid")
                return None

    # Prepare seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    seed = int(seed)

    # data points: x, v, xIneqMin, vIneqMin, xIneqMax, vIneqMax
    dataPointSet = []

    # data point set from x, v
    aggregate_data_by_simul = False
    if x is not None:
        if aggregate_data_op == 'krige' or aggregate_data_op == 'sgs':
            if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model with non-stationary weight or range cannot be used with `aggregate_data_op`='{aggregate_data_op}'")
                return None
            if cov_model.is_orientation_stationary():
                cov_model_agg = cov_model
            else:
                cov_model_agg = gcm.copyCovModel(cov_model)
                cov_model_agg.set_alpha(0.0)
                cov_model_agg.set_beta(0.0)
                cov_model_agg.set_gamma(0.0)
            # Get grid cell with at least one data point:
            # x_agg: 2D array, each row contains the coordinates of the center of such cell
            im_tmp = img.imageFromPoints(x, values=None, varname=None,
                                         nx=nx, ny=ny, nz=nz, sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz,
                                         indicator_var=True, count_var=False)
            ind_agg = np.where(im_tmp.val[0])
            if len(ind_agg[0]) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None
            x_agg = np.array((im_tmp.xx()[ind_agg].reshape(-1), im_tmp.yy()[ind_agg].reshape(-1), im_tmp.zz()[ind_agg].reshape(-1))).T
            # x_agg = np.array((im_tmp.xx()[*ind_agg].reshape(-1), im_tmp.yy()[*ind_agg].reshape(-1), im_tmp.zz()[*ind_agg].reshape(-1))).T
            del(im_tmp)
            # Compute
            # - kriging estimate (v_agg) and kriging std (v_agg_std) at x_agg,
            # - or nreal simulation(s) (v_agg) at x_agg
            if mean is not None and mean.size > 1:
                mean_x_agg = mean[ind_agg]
                # mean_x_agg = mean[*ind_agg]
            else:
                mean_x_agg = mean
            if var is not None and var.size > 1:
                var_x_agg = var[ind_agg]
                # var_x_agg = var[*ind_agg]
            else:
                var_x_agg = var
            if isinstance(cov_model.alpha, np.ndarray) and cov_model.alpha.size == nxyz:
                alpha_x_agg = cov_model.alpha[ind_agg]
                # alpha_x_agg = cov_model.alpha[*ind_agg]
            else:
                alpha_x_agg = cov_model.alpha
            if isinstance(cov_model.beta, np.ndarray) and cov_model.beta.size == nxyz:
                beta_x_agg = cov_model.beta[ind_agg]
                # beta_x_agg = cov_model.beta[*ind_agg]
            else:
                beta_x_agg = cov_model.beta
            if isinstance(cov_model.gamma, np.ndarray) and cov_model.gamma.size == nxyz:
                gamma_x_agg = cov_model.gamma[ind_agg]
                # gamma_x_agg = cov_model.gamma[*ind_agg]
            else:
                gamma_x_agg = cov_model.gamma
            # Set parameters `nneighborMax` from the arguments if not given in `aggregate_data_op_kwargs`
            if 'nneighborMax' not in aggregate_data_op_kwargs.keys():
                aggregate_data_op_kwargs['nneighborMax'] = nneighborMax
            if aggregate_data_op == 'krige':
                try:
                    v_agg, v_agg_std = gcm.krige(x, v, x_agg, cov_model_agg, method=method,
                                                 mean_x=mean_x, mean_xu=mean_x_agg,
                                                 var_x=var_x, var_xu=var_x_agg,
                                                 alpha_xu=alpha_x_agg, beta_xu=beta_x_agg, gamma_xu=gamma_x_agg,
                                                 verbose=0, **aggregate_data_op_kwargs)
                except:
                    if verbose > 0:
                        print(f"ERROR ({fname}): kriging error")
                    return None
            else:
                aggregate_data_by_simul = True
                v_agg = gcm.sgs(x, v, x_agg, cov_model_agg, method=method,
                                mean_x=mean_x, mean_xu=mean_x_agg,
                                var_x=var_x, var_xu=var_x_agg,
                                alpha_xu=alpha_x_agg, beta_xu=beta_x_agg, gamma_xu=gamma_x_agg,
                                nreal=nreal, seed=seed,
                                verbose=0, **aggregate_data_op_kwargs)
                if v_agg is None:
                    if verbose > 0:
                        print(f"ERROR ({fname}): sgs error")
                    return None
            xx_agg, yy_agg, zz_agg = x_agg.T
        elif aggregate_data_op == 'random':
            aggregate_data_by_simul = True
            # Aggregate data on grid cell by taking random point
            xx, yy, zz = x.T
            # first realization of v_agg
            xx_agg, yy_agg, zz_agg, v_agg, i_inv = img.aggregateDataPointsWrtGrid(
                                                    xx, yy, zz, v,
                                                    nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                    op=aggregate_data_op, return_inverse=True,
                                                    **aggregate_data_op_kwargs)
            if len(xx_agg) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None
            # next realizations of v_agg
            v_agg = np.vstack((v_agg, np.zeros((nreal-1, v_agg.size))))
            for i in range(1, nreal):
                v_agg[i] = [v[np.random.choice(np.where(i_inv==j)[0])] for j in range(len(xx_agg))]
        else:
            # Aggregate data on grid cell by using the given operation
            xx, yy, zz = x.T
            try:
                xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                    xx, yy, zz, v,
                                                    nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                    op=aggregate_data_op, **aggregate_data_op_kwargs)
            except:
                if verbose > 0:
                    print(f"ERROR ({fname}): data aggregation (`aggregate_data_op='{aggregate_data_op}'`) failed")
                return None
            if len(xx_agg) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None

        if xIneqMin is not None or xIneqMax is not None:
            # Get single grid index for data points
            ix, iy, iz = img.pointToGridIndex(xx_agg, yy_agg, zz_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

        if not aggregate_data_by_simul:
            dataPointSet.append(
                PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
                )
        else:
            # Integrate data points from sgs index 0
            dataPointSet.append(
                PointSet(npt=v_agg.shape[1], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg[0])), varname=['X', 'Y', 'Z', varname])
                )

    # data point set from xIneqMin, vIneqMin
    if xIneqMin is not None:
        # Aggregate data on grid cell by using the given operation
        xx, yy, zz = xIneqMin.T
        try:
            xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg, v_ineqMin_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, vIneqMin,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op=aggregate_data_ineqMin_op, **aggregate_data_ineqMin_op_kwargs)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): inequality data (min) aggregation (`aggregate_data_op='{aggregate_data_ineqMin_op}'`) failed")
            return None
        if x is not None:
            # Get single grid index for inequality (min) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMin = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index with points from `x` and `xIneqMin`
            ig_inter, ig1, ig2 = np.intersect1d(ig, ig_ineqMin, assume_unique=True, return_indices=True)

            if ig_inter.size:
                if verbose > 1:
                    print(f'WARNING ({fname}): {ig_inter.size} grid cell(s) have both "inequality (min)" and "equality" data: inequlity data has been removed')
                    if not aggregate_data_by_simul:
                        ninconsistent = (v_agg[ig1] < v_ineqMin_agg[ig2]).sum()
                        if ninconsistent:
                            print(f'WARNING ({fname}): {ninconsistent} "inequality (min)" found')
                # Remove redundant points from inequality data set
                xx_ineqMin_agg = np.delete(xx_ineqMin_agg, ig2)
                yy_ineqMin_agg = np.delete(yy_ineqMin_agg, ig2)
                zz_ineqMin_agg = np.delete(zz_ineqMin_agg, ig2)
                v_ineqMin_agg = np.delete(v_ineqMin_agg, ig2)

        if v_ineqMin_agg.shape[0]:
            dataPointSet.append(
                PointSet(npt=v_ineqMin_agg.shape[0], nv=4, val=np.array((xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg, v_ineqMin_agg)), varname=['X', 'Y', 'Z', '{}_min'.format(varname)])
                )
        else:
            if verbose > 1:
                print(f"WARNING ({fname}): no inequality (min) data point in grid")
            xIneqMin = None

    # data point set from xIneqMax, vIneqMax
    if xIneqMax is not None:
        # Aggregate data on grid cell by using the given operation
        xx, yy, zz = xIneqMax.T
        try:
            xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg, v_ineqMax_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, vIneqMax,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op=aggregate_data_ineqMax_op, **aggregate_data_ineqMax_op_kwargs)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): inequality data (max) aggregation (`aggregate_data_op='{aggregate_data_ineqMax_op}'`) failed")
            return None
        if x is not None:
            # Get single grid index for inequality (max) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMax = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index with points from `x` and `xIneqMax`
            ig_inter, ig1, ig2 = np.intersect1d(ig, ig_ineqMax, assume_unique=True, return_indices=True)

            if ig_inter.size:
                if verbose > 1:
                    print(f'WARNING ({fname}): {ig_inter.size} grid cell(s) have both "inequality (max)" and "equality" data: inequlity data has been removed')
                    if not aggregate_data_by_simul:
                        ninconsistent = (v_agg[ig1] > v_ineqMax_agg[ig2]).sum()
                        if ninconsistent:
                            print(f'WARNING ({fname}): {ninconsistent} "inequality (max)" found')
                # Remove redundant points from inequality data set
                xx_ineqMax_agg = np.delete(xx_ineqMax_agg, ig2)
                yy_ineqMax_agg = np.delete(yy_ineqMax_agg, ig2)
                zz_ineqMax_agg = np.delete(zz_ineqMax_agg, ig2)
                v_ineqMax_agg = np.delete(v_ineqMax_agg, ig2)

        if xIneqMin is not None:
            # Get single grid index for inequality (min) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMin = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index for inequality (max) data points
            ix, iy, iz = img.pointToGridIndex(xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg,
                                              sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz)
            ig_ineqMax = img.gridIndexToSingleGridIndex(ix, iy, iz, nx, ny, nz)

            # Get single grid index with points from `xIneqMin` and `xIneqMax`
            ig_inter, ig1, ig2 = np.intersect1d(ig_ineqMin, ig_ineqMax, assume_unique=True, return_indices=True)

            if ig_inter.size:
                ii = np.where(v_ineqMin_agg[ig1] > v_ineqMax_agg[ig2])[0]
                if len(ii):
                    if verbose > 0:
                        print(f'ERROR ({fname}): {len(ii)} grid cell(s) have inconsistent "inequality min" and "inequality max" data')
                    return None
                    # if verbose > 1:
                    #     print(f'WARNING ({fname}): {len(ii)} grid cell(s) have inconsistent "inequality min" and "inequality max" data: inequlity max data has been removed')
                    # ig2 = ig2[ii]
                    # # Remove inconsistent inequality max
                    # xx_ineqMax_agg = np.delete(xx_ineqMax_agg, ig2)
                    # yy_ineqMax_agg = np.delete(yy_ineqMax_agg, ig2)
                    # zz_ineqMax_agg = np.delete(zz_ineqMax_agg, ig2)
                    # v_ineqMax_agg = np.delete(v_ineqMax_agg, ig2)

        if v_ineqMax_agg.shape[0]:
            dataPointSet.append(
                PointSet(npt=v_ineqMax_agg.shape[0], nv=4, val=np.array((xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg, v_ineqMax_agg)), varname=['X', 'Y', 'Z', '{}_max'.format(varname)])
                )
        else:
            if verbose > 1:
                print(f"WARNING ({fname}): no inequality (max) data point in grid")
            xIneqMax = None

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if xIneqMin is not None:
            pts = np.vstack((pts, np.array((xx_ineqMin_agg, yy_ineqMin_agg, zz_ineqMin_agg)).T))
        if xIneqMax is not None:
            pts = np.vstack((pts, np.array((xx_ineqMax_agg, yy_ineqMax_agg, zz_ineqMax_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # Prepare seed (for simulation in grid)
    seed = seed + 986 # same increment (whatever the number or realization done in sgs above)

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if not aggregate_data_by_simul:
        # --- Fill mpds_geosClassicInput structure (C)
        mpds_geosClassicInput, flag = fill_mpds_geosClassicInput(
            space_dim,
            cov_model,
            nx, ny, nz,
            sx, sy, sz,
            ox, oy, oz,
            varname,
            outputReportFile,
            computationMode,
            None,
            dataPointSet,
            mask,
            mean,
            var,
            searchRadiusRelative,
            nneighborMax,
            searchNeighborhoodSortMode,
            nGibbsSamplerPathMin,
            nGibbsSamplerPathMax,
            seed,
            nreal)

        if not flag:
            if verbose > 0:
                print(f'ERROR ({fname}): can not fill input structure!')
            return None

        # --- Prepare mpds_geosClassicIOutput structure (C)
        # Allocate mpds_geosClassicOutput
        mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

        # Init mpds_geosClassicOutput
        geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

        # --- Set progress monitor
        mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
        geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

        # Set function to update progress monitor:
        # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
        # the function
        #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
        # should be used, but the following function can also be used:
        #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
        #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
        if verbose < 3:
            mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
        else:
            mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

        # # --- Set number of threads
        # if nthreads <= 0:
        #     nth = max(os.cpu_count() + nthreads, 1)
        # else:
        #     nth = nthreads

        if verbose >= 2:
            print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
            sys.stdout.flush()
            sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

        # --- Launch "GeosClassicSim" (launch C code)
        # err = geosclassic.MPDSGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
        err = geosclassic.MPDSOMPGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

        # Free memory on C side: mpds_geosClassicInput
        geosclassic.MPDSGeosClassicFreeGeosClassicInput(mpds_geosClassicInput)
        #geosclassic.MPDSFree(mpds_geosClassicInput)
        geosclassic.free_MPDS_GEOSCLASSICINPUT(mpds_geosClassicInput)

        if err:
            if verbose > 0:
                err_message = geosclassic.mpds_get_error_message(-err)
                err_message = err_message.replace('\n', '')
                print(err_message)
            geosclassic_output = None
        else:
            geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

        # Free memory on C side: mpds_geosClassicOutput
        geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
        #geosclassic.MPDSFree(mpds_geosClassicOutput)
        geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

        # Free memory on C side: mpds_progressMonitor
        #geosclassic.MPDSFree(mpds_progressMonitor)
        geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    else:
        # Equality data values will change for each realization
        if verbose >= 2:
            print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
            sys.stdout.flush()
            sys.stdout.flush() # twice!, so that the previous print is flushed before launching geos-classic...

        # Initialization of image and warnings for storing results
        image = Img(nx=nx, ny=ny, nz=nz, sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz, nv=nreal, val=np.nan)
        nwarning = 0
        warnings = []
        outputReportFile_ir = None # default
        for ir in range(nreal):
            if ir > 0:
                # Set equality data values for realization index ir
                dataPointSet[0].val[3] = v_agg[ir]

            if outputReportFile is not None:
                outputReportFile_ir = outputReportFile + f'.{ir}'

            # --- Fill mpds_geosClassicInput structure (C)
            mpds_geosClassicInput, flag = fill_mpds_geosClassicInput(
                space_dim,
                cov_model,
                nx, ny, nz,
                sx, sy, sz,
                ox, oy, oz,
                varname,
                outputReportFile_ir,
                computationMode,
                None,
                dataPointSet,
                mask,
                mean,
                var,
                searchRadiusRelative,
                nneighborMax,
                searchNeighborhoodSortMode,
                nGibbsSamplerPathMin,
                nGibbsSamplerPathMax,
                seed+ir, # seed for realization index ir
                1) # one real

            if not flag:
                if verbose > 0:
                    print(f'ERROR ({fname}): can not fill input structure!')
                return None

            # --- Prepare mpds_geosClassicIOutput structure (C)
            # Allocate mpds_geosClassicOutput
            mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

            # Init mpds_geosClassicOutput
            geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

            # --- Set progress monitor
            mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
            geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

            # Set function to update progress monitor:
            # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
            # the function
            #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
            # should be used, but the following function can also be used:
            #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
            #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
            mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
            # if verbose < 3:
            #     mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
            # else:
            #     mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
            #
            # if verbose >= 2:
            #     print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
            #     sys.stdout.flush()
            #     sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

            # --- Launch "GeosClassicSim" (launch C code)
            # err = geosclassic.MPDSGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
            err = geosclassic.MPDSOMPGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

            # Free memory on C side: mpds_geosClassicInput
            geosclassic.MPDSGeosClassicFreeGeosClassicInput(mpds_geosClassicInput)
            #geosclassic.MPDSFree(mpds_geosClassicInput)
            geosclassic.free_MPDS_GEOSCLASSICINPUT(mpds_geosClassicInput)

            if err:
                if verbose > 0:
                    err_message = geosclassic.mpds_get_error_message(-err)
                    err_message = err_message.replace('\n', '')
                    print(err_message)
                geosclassic_output = None
            else:
                geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

            # Free memory on C side: mpds_geosClassicOutput
            geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
            #geosclassic.MPDSFree(mpds_geosClassicOutput)
            geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

            # Free memory on C side: mpds_progressMonitor
            #geosclassic.MPDSFree(mpds_progressMonitor)
            geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

            if geosclassic_output is not None:
                image.val[ir] = geosclassic_output['image'].val[0]
                nwarning = nwarning + geosclassic_output['nwarning']
                warnings.extend(geosclassic_output['warnings'])

            del(geosclassic_output)

        # Remove duplicated warnings
        warnings = list(np.unique(warnings))

        # Rename variables
        ndigit = geosclassic.MPDS_GEOS_CLASSIC_NB_DIGIT_FOR_REALIZATION_NUMBER
        for j in range(image.nv):
            image.varname[j] = image.varname[j][:-ndigit] + f'{j:0{ndigit}d}'

        # Set geosclassic_output
        geosclassic_output = {'image':image, 'nwarning':nwarning, 'warnings':warnings}

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulate3D_mp(
        cov_model,
        dimension, spacing=(1.0, 1.0, 1.0), origin=(0.0, 0.0, 0.0),
        method='simple_kriging',
        nreal=1,
        mean=None, var=None,
        x=None, v=None,
        xIneqMin=None, vIneqMin=None,
        xIneqMax=None, vIneqMax=None,
        aggregate_data_op=None,
        aggregate_data_op_kwargs=None,
        aggregate_data_ineqMin_op='max',
        aggregate_data_ineqMin_op_kwargs=None,
        aggregate_data_ineqMax_op='min',
        aggregate_data_ineqMax_op_kwargs=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.0,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        nGibbsSamplerPathMin=50,
        nGibbsSamplerPathMax=200,
        seed=None,
        outputReportFile=None,
        treat_image_one_by_one=False,
        nproc=None, nthreads_per_proc=None,
        verbose=2):
    """
    Computes the same as the function `simulate3D`, using multiprocessing.

    All the parameters are the same as those of the function `simulate3D`,
    except `nthreads` that is replaced by the parameters `nproc` and
    `nthreads_per_proc`, and an extra parameter `treat_image_one_by_one`.

    This function launches multiple processes (based on `multiprocessing`
    package):
    - `nproc` parallel processes using each one `nthreads_per_proc` threads
    are launched [parallel calls of the function `simulate3D`];
    - the set of realizations (specified by `nreal`) is distributed in a
    balanced way over the processes;
    - in terms of resources, this implies the use of `nproc*nthreads_per_proc`
    cpu(s).

    Parameters
    ----------
    (new parameters)
    nproc : int, optional
        number of processes; by default (`None`):
        `nproc` is set to `min(nmax-1, nreal)` (but at least 1), where nmax is
        the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    nthreads_per_proc : int, optional
        number of thread(s) per process (should be > 0); by default (`None`):
        `nthreads_per_proc` is automatically computed as the maximal integer
        (but at least 1) such that `nproc*nthreads_per_proc <= nmax-1`, where
        nmax is the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    treat_image_one_by_one : bool, default: False
        keyword argument passed to the function `geone.img.gatherImages`:
        - if True: images (result of each process) are gathered one by one,
        i.e. the variables of each image are inserted in an output image one by
        one and removed from the source (slower, may save memory)
        - if False: images (result of each process) are gathered at once,
        i.e. the variables of all images are inserted in an output image at once,
        and then removed (faster)

    See function `simulate3D`.
    """
    # fname = 'simulate3D_mp'

    # Set number of processes: nproc
    if nproc is None:
        nproc = max(min(multiprocessing.cpu_count()-1, nreal), 1)
    else:
        nproc_tmp = nproc
        nproc = max(min(int(nproc), nreal), 1)
        if verbose > 0 and nproc != nproc_tmp:
            print('NOTE: number of processes has been changed (now: nproc={})'.format(nproc))

    # Set number of threads per process: nth
    if nthreads_per_proc is None:
        nth = max(int(np.floor((multiprocessing.cpu_count()-1) / nproc)), 1)
    else:
        nth = max(int(nthreads_per_proc), 1)
        if verbose > 0 and nth != nthreads_per_proc:
            print('NOTE: number of threads per process has been changed (now: nthreads_per_proc={})'.format(nth))

    if verbose > 0 and nproc * nth > multiprocessing.cpu_count():
        print('NOTE: total number of cpu(s) used will exceed number of cpu(s) of the system...')

    # Set the distribution of the realizations over the processes
    # Condider the Euclidean division of nreal by nproc:
    #     nreal = q * nproc + r, with 0 <= r < nproc
    # Then, (q+1) realizations will be done on process 0, 1, ..., r-1, and q realization on process r, ..., nproc-1
    # Define the list real_index_proc of length (nproc+1) such that
    #   real_index_proc[i], ..., real_index_proc[i+1] - 1 : are the realization indices run on process i
    q, r = np.divmod(nreal, nproc)
    real_index_proc = [i*q + min(i, r) for i in range(nproc+1)]

    if verbose >= 2:
        print('Geos-Classic running on {} process(es)... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(nproc, geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching geos-classic...

    # Prepare seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    seed = int(seed)

    outputReportFile_p = None

    # Set pool of nproc workers
    pool = multiprocessing.Pool(nproc)
    out_pool = []
    for i in range(nproc):
        # Adapt input for i-th process
        nreal_p = real_index_proc[i+1] - real_index_proc[i]
        seed_p = seed + real_index_proc[i]
        if outputReportFile is not None:
            outputReportFile_p = outputReportFile + f'.{i}'
        if i==0:
            verbose_p = min(verbose, 1) # allow to print error for process i
        else:
            verbose_p = 0
        # Launch geos-classic (i-th process)
        out_pool.append(
            pool.apply_async(simulate3D,
                args=(cov_model,
                dimension, spacing, origin,
                method,
                nreal_p,                     # nreal (adjusted)
                mean, var,
                x, v,
                xIneqMin, vIneqMin,
                xIneqMax, vIneqMax,
                aggregate_data_op,
                aggregate_data_op_kwargs,
                aggregate_data_ineqMin_op,
                aggregate_data_ineqMin_op_kwargs,
                aggregate_data_ineqMax_op,
                aggregate_data_ineqMax_op_kwargs,
                mask,
                add_data_point_to_mask,
                searchRadiusRelative,
                nneighborMax,
                searchNeighborhoodSortMode,
                nGibbsSamplerPathMin,
                nGibbsSamplerPathMax,
                seed_p,                      # seed (adjusted)
                outputReportFile_p,          # outputReportFile (adjusted)
                nth,                         # nthreads
                verbose_p)                   # verbose (adjusted)
                )
            )

    # Properly end working process
    pool.close() # Prevents any more tasks from being submitted to the pool,
    pool.join()  # then, wait for the worker processes to exit.

    # Get result from each process
    geosclassic_output_proc = [p.get() for p in out_pool]

    if np.any([out is None for out in geosclassic_output_proc]):
        return None

    # Gather results from every process
    # image
    image = []
    for out in geosclassic_output_proc:
        if out['image'] is not None:
            image.append(out['image'])
            del(out['image'])
    if len(image) == 0:
        image = None
    # Gather images and adjust variable names
    all_image = img.gatherImages(image, keep_varname=True, rem_var_from_source=True, treat_image_one_by_one=treat_image_one_by_one)
    ndigit = geosclassic.MPDS_GEOS_CLASSIC_NB_DIGIT_FOR_REALIZATION_NUMBER
    for j in range(all_image.nv):
        all_image.varname[j] = all_image.varname[j][:-ndigit] + f'{j:0{ndigit}d}'

    # nwarning
    nwarning = np.sum([out['nwarning'] for out in geosclassic_output_proc])
    # warnings
    warnings = list(np.unique(np.hstack([out['warnings'] for out in geosclassic_output_proc])))

    geosclassic_output = {'image':all_image, 'nwarning':nwarning, 'warnings':warnings}

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete (all process(es))')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def estimate1D(
        cov_model,
        dimension, spacing=1.0, origin=0.0,
        method='simple_kriging',
        mean=None, var=None,
        x=None, v=None,
        aggregate_data_op=None,
        aggregate_data_op_kwargs=None,
        mask=None,
        add_data_point_to_mask=True,
        use_unique_neighborhood=False,
        searchRadiusRelative=1.0,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Computes kriging estimates and standard deviations in 1D.

    Interpolation takes place in (center of) grid cells, based on simple or
    ordinary kriging.

    Parameters
    ----------
    cov_model : :class:`geone.CovModel.CovModel1D`
        covariance model in 1D
    dimension : int
        `dimension=nx`, number of cells in the 1D simulation grid
    spacing : float, default: 1.0
        `spacing=sx`, cell size
    origin : float, default: 0.0
        `origin=ox`, origin of the 1D simulation grid (left border)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    mean : function (callable), or array-like of floats, or float, optional
        kriging mean value:
        - if a function: function of one argument (xi) that returns the mean at
        location xi
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), mean values at grid cells (for
        non-stationary mean)
        - if a float: same mean value at every grid cell
        - by default (`None`): the mean of data value (`v`) (0.0 if no data) is
        considered at every grid cell
    var : function (callable), or array-like of floats, or float, optional
        kriging variance value:
        - if a function: function of one argument (xi) that returns the variance
        at location xi
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), variance values at grid cells (for
        non-stationary variance)
        - if a float: same variance value at every grid cell
        - by default (`None`): not used (use of covariance model only)
    x : 1D array-like of floats, optional
        data points locations (float coordinates); note: if one point, a float
        is accepted
    v : 1D array-like of floats, optional
        data values at `x` (`v[i]` is the data value at `x[i]`), array of same
        length as `x` (or float if one point)
    aggregate_data_op : str {'krige', 'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, optional
        operation used to aggregate data points falling in the same grid cells;
        - if `aggregate_data_op='krige'`: function `geone.covModel.krige` is used
        with the covariance model `cov_model` given in arguments, as well as
        the parameters `use_unique_neighborhood`, `nneighborMax` given in
        arguments unless they are given in `aggregate_data_op_kwargs`
        - if `aggregate_data_op='most_freq'`: most frequent value is selected
        (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_op='random'`: value from a random point is selected
        - otherwise: the function `numpy.<aggregate_data_op>` is used with the
        additional parameters given by `aggregate_data_op_kwargs`, note that, e.g.
        `aggregate_data_op='quantile'` requires the additional parameter
        `q=<quantile_to_compute>`;
        by default: if covariance model has stationary ranges and weight (sill),
        `aggregate_data_op='krige'` is used, otherwise `aggregate_data_op='mean'`
    aggregate_data_op_kwargs : dict, optional
        keyword arguments to be passed to `geone.covModel.krige` or
        `numpy.<aggregate_data_op>`, according to the parameter
        `aggregate_data_op`
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    use_unique_neighborhood : bool, default: False
        indicates if a unique neighborhood is used:
        - if True: all data points are taken into account for computing
        estimates and standard deviations; in this case: parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode` are
        not used
        - if False: only data points within a search ellipsoid are taken into
        account for computing estimates and standard deviations (see parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode`)
    searchRadiusRelative : float, default: 1.0
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=2` variables (estimates and standard
            deviations);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'estimate1D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = dimension, 1, 1
    sx, sy, sz = spacing, 1.0, 1.0
    ox, oy, oz = origin, 0.0, 0.0

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 1

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # cov_model
    if not isinstance(cov_model, gcm.CovModel1D):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model` is not valid")
        return None

    for el in cov_model.elem:
        # weight
        w = el[1]['w']
        if np.size(w) != 1 and np.size(w) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): `cov_model`: weight ('w') not compatible with simulation grid")
            return None
        # ranges
        if 'r' in el[1].keys():
            r  = el[1]['r']
            if np.size(r) != 1 and np.size(r) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): `cov_model`: range ('r') not compatible with simulation grid")
                return None
        # additional parameter (s)
        if 's' in el[1].keys():
            s  = el[1]['s']
            if np.size(s) != 1 and np.size(s) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): `cov_model`: parameter ('s') not compatible with simulation grid")
                return None

    # aggregate_data_op (default)
    if aggregate_data_op is None:
        if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
            aggregate_data_op = 'mean'
        else:
            aggregate_data_op = 'krige'

    if aggregate_data_op_kwargs is None:
        aggregate_data_op_kwargs = {}

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 1
    elif method == 'ordinary_kriging':
        computationMode = 0
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # If unique neighborhood is used, set searchRadiusRelative to -1
    #    (and initialize nneighborMax, searchNeighborhoodSortMode (unused))
    if use_unique_neighborhood:
        searchRadiusRelative = -1.0
        nneighborMax = 1
        searchNeighborhoodSortMode = 0

    else:
       # Check parameters - searchRadiusRelative
       if searchRadiusRelative < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
           if verbose > 0:
               print(f"ERROR ({fname}): 'searchRadiusRelative' too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
           return None

       # Check parameters - nneighborMax
       if nneighborMax != -1 and nneighborMax <= 0:
           if verbose > 0:
               print(f"ERROR ({fname}): `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
           return None

       # Check parameters - searchNeighborhoodSortMode
       if searchNeighborhoodSortMode is None:
           # set greatest possible value
           if cov_model.is_stationary():
               searchNeighborhoodSortMode = 2
           else:
               searchNeighborhoodSortMode = 1
       else:
           if searchNeighborhoodSortMode == 2:
               if not cov_model.is_stationary():
                   if verbose > 0:
                       print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                   return None

       # if searchNeighborhoodSortMode is None:
       #     # set greatest possible value
       #     if cov_model.is_stationary():
       #         searchNeighborhoodSortMode = 2
       #     elif cov_model.is_orientation_stationary() and cov_model.is_range_stationary():
       #         searchNeighborhoodSortMode = 1
       #     else:
       #         searchNeighborhoodSortMode = 0
       # else:
       #     if searchNeighborhoodSortMode == 2:
       #         if not cov_model.is_stationary():
       #             if verbose > 0:
       #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
       #             return None
       #     elif searchNeighborhoodSortMode == 1:
       #         if not cov_model.is_orientation_stationary() or not cov_model.is_range_stationary():
       #             if verbose > 0:
       #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
       #             return None

    # Preparation of data points
    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 1) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

    # Check parameters - mean
    mean_x = mean
    if mean is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying `mean` not allowed with ordinary kriging")
        #     return None
        if callable(mean):
            if x is not None:
                mean_x = mean(x[:, 0])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            mean = mean(xi) # replace function 'mean' by its evaluation on the grid
        else:
            mean = np.asarray(mean, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if mean.size == 1:
                if x is not None:
                    mean_x = mean
            elif mean.size == nxyz:
                # mean = mean.reshape(nx)
                if x is not None:
                    mean_x = img.Img_interp_func(img.Img(nx, 1, 1, sx, 1., 1., ox, 0., 0., nv=1, val=mean), iy=0, iz=0)(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `mean` is not valid")
                return None

    # Check parameters - var
    var_x = var
    if var is not None:
        if method == 'ordinary_kriging':
            if verbose > 0:
                print(f"ERROR ({fname}): specifying 'var' not allowed with ordinary kriging")
            return None
        if callable(var):
            if x is not None:
                var_x = var(x[:, 0])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            var = var(xi) # replace function 'var' by its evaluation on the grid
        else:
            var = np.asarray(var, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if var.size == 1:
                if x is not None:
                    var_x = var
            elif var.size == nxyz:
                # var = var.reshape(nx)
                if x is not None:
                    var_x = img.Img_interp_func(img.Img(nx, 1, 1, sx, 1., 1., ox, 0., 0., nv=1, val=var), iy=0, iz=0)(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `var` is not valid")
                return None

    # data points: x, v
    dataPointSet = []

    # data point set from x, v
    if x is not None:
        if aggregate_data_op == 'krige':
            if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model with non-stationary weight or range cannot be used with `aggregate_data_op`='{aggregate_data_op}'")
                return None
            cov_model_agg = cov_model
            # Get grid cell with at least one data point:
            # x_agg: 2D array, each row contains the coordinates of the center of such cell
            im_tmp = img.imageFromPoints(x, values=None, varname=None,
                                         nx=nx, sx=sx, ox=ox,
                                         indicator_var=True, count_var=False)
            ind_agg = np.where(im_tmp.val[0])
            if len(ind_agg[0]) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None
            x_agg = im_tmp.xx()[ind_agg].reshape(-1, 1)
            # x_agg = im_tmp.xx()[*ind_agg].reshape(-1, 1)
            ind_agg = ind_agg[2:] # remove index along z and y axes
            del(im_tmp)
            # Compute kriging estimate (v_agg) and kriging std (v_agg_std) at x_agg
            if mean is not None and mean.size > 1:
                mean_x_agg = mean[ind_agg]
                # mean_x_agg = mean[*ind_agg]
            else:
                mean_x_agg = mean
            if var is not None and var.size > 1:
                var_x_agg = var[ind_agg]
                # var_x_agg = var[*ind_agg]
            else:
                var_x_agg = var
            # Set parameters `use_unique_neighborhood` and `nneighborMax`
            # from the arguments if not given in `aggregate_data_op_kwargs`
            if 'use_unique_neighborhood' not in aggregate_data_op_kwargs.keys():
                aggregate_data_op_kwargs['use_unique_neighborhood'] = use_unique_neighborhood
            if 'nneighborMax' not in aggregate_data_op_kwargs.keys():
                aggregate_data_op_kwargs['nneighborMax'] = nneighborMax
            try:
                v_agg, v_agg_std = gcm.krige(x, v, x_agg, cov_model_agg, method=method,
                                             mean_x=mean_x, mean_xu=mean_x_agg,
                                             var_x=var_x, var_xu=var_x_agg,
                                             verbose=0, **aggregate_data_op_kwargs)
            except:
                if verbose > 0:
                    print(f"ERROR ({fname}): kriging error")
                return None
            xx_agg = x_agg[:, 0]
            yy_agg = np.ones_like(xx_agg) * oy + 0.5 * sy
            zz_agg = np.ones_like(xx_agg) * oz + 0.5 * sz
        else:
            # Aggregate data on grid cell by using the given operation
            xx = x[:, 0]
            yy = np.ones_like(xx) * oy + 0.5 * sy
            zz = np.ones_like(xx) * oz + 0.5 * sz
            try:
                xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                    xx, yy, zz, v,
                                                    nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                    op=aggregate_data_op, **aggregate_data_op_kwargs)
            except:
                if verbose > 0:
                    print(f"ERROR ({fname}): data aggregation (`aggregate_data_op='{aggregate_data_op}'`) failed")
                return None
            if len(xx_agg) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None

        dataPointSet.append(
            PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
            )

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # --- Fill mpds_geosClassicInput structure (C)
    mpds_geosClassicInput, flag = fill_mpds_geosClassicInput(
        space_dim,
        cov_model,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        outputReportFile,
        computationMode,
        None,
        dataPointSet,
        mask,
        mean,
        var,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        0,
        0,
        0,
        0)

    if not flag:
        if verbose > 0:
            print(f'ERROR ({fname}): can not fill input structure!')
        return None

    # --- Prepare mpds_geosClassicIOutput structure (C)
    # Allocate mpds_geosClassicOutput
    mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

    # Init mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

    # --- Set progress monitor
    mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
    geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

    # Set function to update progress monitor:
    # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
    # the function
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
    # should be used, but the following function can also be used:
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
    if verbose < 3:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
    else:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if verbose >= 2:
        print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

    # --- Launch "GeosClassicSim" (launch C code)
    # err = geosclassic.MPDSGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
    err = geosclassic.MPDSOMPGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

    # Free memory on C side: mpds_geosClassicInput
    geosclassic.MPDSGeosClassicFreeGeosClassicInput(mpds_geosClassicInput)
    #geosclassic.MPDSFree(mpds_geosClassicInput)
    geosclassic.free_MPDS_GEOSCLASSICINPUT(mpds_geosClassicInput)

    if err:
        if verbose > 0:
            err_message = geosclassic.mpds_get_error_message(-err)
            err_message = err_message.replace('\n', '')
            print(err_message)
        geosclassic_output = None
    else:
        geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

    # Free memory on C side: mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
    #geosclassic.MPDSFree(mpds_geosClassicOutput)
    geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

    # Free memory on C side: mpds_progressMonitor
    #geosclassic.MPDSFree(mpds_progressMonitor)
    geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    if geosclassic_output is not None and x is not None and aggregate_data_op == 'krige':
        # Set kriging standard deviation at grid cell containing a data
        geosclassic_output['image'].val[1, 0, 0, ind_agg[0]] = v_agg_std
        # geosclassic_output['image'].val[1, 0, 0, *ind_agg] = v_agg_std

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def estimate2D(
        cov_model,
        dimension, spacing=(1.0, 1.0), origin=(0.0, 0.0),
        method='simple_kriging',
        mean=None, var=None,
        x=None, v=None,
        aggregate_data_op=None,
        aggregate_data_op_kwargs=None,
        mask=None,
        add_data_point_to_mask=True,
        use_unique_neighborhood=False,
        searchRadiusRelative=1.0,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Computes kriging estimates and standard deviations in 2D.

    Interpolation takes place in (center of) grid cells, based on simple or
    ordinary kriging.

    Parameters
    ----------
    cov_model : :class:`geone.CovModel.CovModel2D`
        covariance model in 2D
    dimension : 2-tuple of ints
        `dimension=(nx, ny)`, number of cells in the 2D simulation grid along
        each axis
    spacing : 2-tuple of floats, default: (1.0, 1.0)
        `spacing=(sx, sy)`, cell size along each axis
    origin : 2-tuple of floats, default: (0.0, 0.0)
        `origin=(ox, oy)`, origin of the 2D simulation grid (lower-left corner)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    mean : function (callable), or array-like of floats, or float, optional
        kriging mean value:
        - if a function: function of two arguments (xi, yi) that returns the mean
        at location (xi, yi)
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), mean values at grid cells (for
        non-stationary mean)
        - if a float: same mean value at every grid cell
        - by default (`None`): the mean of data value (`v`) (0.0 if no data) is
        considered at every grid cell
    var : function (callable), or array-like of floats, or float, optional
        kriging variance value:
        - if a function: function of two arguments (xi, yi) that returns the
        variance at location (xi, yi)
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), variance values at grid cells (for
        non-stationary variance)
        - if a float: same variance value at every grid cell
        - by default (`None`): not used (use of covariance model only)
    x : 2D array of floats of shape (n, 2), optional
        data points locations, with n the number of data points, each row of `x`
        is the float coordinates of one data point; note: if n=1, a 1D array of
        shape (2,) is accepted
    v : 1D array of floats of shape (n,), optional
        data values at `x` (`v[i]` is the data value at `x[i]`)
    aggregate_data_op : str {'krige', 'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, optional
        operation used to aggregate data points falling in the same grid cells;
        - if `aggregate_data_op='krige'`: function `geone.covModel.krige` is used
        with the covariance model `cov_model` given in arguments, as well as
        the parameters `use_unique_neighborhood`, `nneighborMax` given in
        arguments unless they are given in `aggregate_data_op_kwargs`
        - if `aggregate_data_op='most_freq'`: most frequent value is selected
        (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_op='random'`: value from a random point is selected
        - otherwise: the function `numpy.<aggregate_data_op>` is used with the
        additional parameters given by `aggregate_data_op_kwargs`, note that, e.g.
        `aggregate_data_op='quantile'` requires the additional parameter
        `q=<quantile_to_compute>`;
        by default: if covariance model has stationary ranges and weight (sill),
        `aggregate_data_op='krige'` is used, otherwise `aggregate_data_op='mean'`
    aggregate_data_op_kwargs : dict, optional
        keyword arguments to be passed to `geone.covModel.krige` or
        `numpy.<aggregate_data_op>`, according to the parameter
        `aggregate_data_op`
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    use_unique_neighborhood : bool, default: False
        indicates if a unique neighborhood is used:
        - if True: all data points are taken into account for computing
        estimates and standard deviations; in this case: parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode` are
        not used
        - if False: only data points within a search ellipsoid are taken into
        account for computing estimates and standard deviations (see parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode`)
    searchRadiusRelative : float, default: 1.0
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=2` variables (estimates and standard
            deviations);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'estimate2D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = *dimension, 1
    sx, sy, sz = *spacing, 1.0
    ox, oy, oz = *origin, 0.0

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 2

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # cov_model
    if isinstance(cov_model, gcm.CovModel1D):
        cov_model = gcm.covModel1D_to_covModel2D(cov_model) # convert model 1D in 2D
            # -> will not be modified cov_model at exit

    if not isinstance(cov_model, gcm.CovModel2D):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model` is not valid")
        return None

    for el in cov_model.elem:
        # weight
        w = el[1]['w']
        if np.size(w) != 1 and np.size(w) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): `cov_model`: weight ('w') not compatible with simulation grid")
            return None
        # ranges
        if 'r' in el[1].keys():
            for r in el[1]['r']:
                if np.size(r) != 1 and np.size(r) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): `cov_model`: range ('r') not compatible with simulation grid")
                    return None
        # additional parameter (s)
        if 's' in el[1].keys():
            s  = el[1]['s']
            if np.size(s) != 1 and np.size(s) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): `cov_model`: parameter ('s') not compatible with simulation grid")
                return None

    # alpha
    angle = cov_model.alpha
    if np.size(angle) != 1 and np.size(angle) != nxyz:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model`: angle (alpha) not compatible with simulation grid")
        return None

    # aggregate_data_op (default)
    if aggregate_data_op is None:
        if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
            aggregate_data_op = 'mean'
        else:
            aggregate_data_op = 'krige'

    if aggregate_data_op_kwargs is None:
        aggregate_data_op_kwargs = {}

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 1
    elif method == 'ordinary_kriging':
        computationMode = 0
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # If unique neighborhood is used, set searchRadiusRelative to -1
    #    (and initialize nneighborMax, searchNeighborhoodSortMode (unused))
    if use_unique_neighborhood:
        searchRadiusRelative = -1.0
        nneighborMax = 1
        searchNeighborhoodSortMode = 0

    else:
       # Check parameters - searchRadiusRelative
       if searchRadiusRelative < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
           if verbose > 0:
               print(f"ERROR ({fname}): `searchRadiusRelative` too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
           return None

       # Check parameters - nneighborMax
       if nneighborMax != -1 and nneighborMax <= 0:
           if verbose > 0:
               print(f"ERROR ({fname}): `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
           return None

       # Check parameters - searchNeighborhoodSortMode
       if searchNeighborhoodSortMode is None:
           # set greatest possible value
           if cov_model.is_stationary():
               searchNeighborhoodSortMode = 2
           else:
               searchNeighborhoodSortMode = 1
       else:
           if searchNeighborhoodSortMode == 2:
               if not cov_model.is_stationary():
                   if verbose > 0:
                       print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                   return None

       # if searchNeighborhoodSortMode is None:
       #     # set greatest possible value
       #     if cov_model.is_stationary():
       #         searchNeighborhoodSortMode = 2
       #     elif cov_model.is_orientation_stationary() and cov_model.is_range_stationary():
       #         searchNeighborhoodSortMode = 1
       #     else:
       #         searchNeighborhoodSortMode = 0
       # else:
       #     if searchNeighborhoodSortMode == 2:
       #         if not cov_model.is_stationary():
       #             if verbose > 0:
       #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
       #             return None
       #     elif searchNeighborhoodSortMode == 1:
       #         if not cov_model.is_orientation_stationary() or not cov_model.is_range_stationary():
       #             if verbose > 0:
       #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
       #             return None

    # Preparation of data points
    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 2) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

    # Check parameters - mean
    mean_x = mean
    if mean is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying `mean` not allowed with ordinary kriging")
        #     return None
        if callable(mean):
            if x is not None:
                mean_x = mean(x[:, 0], x[:, 1])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            yi = oy + sy*(0.5+np.arange(ny)) # y-coordinate of cell center
            yyi, xxi = np.meshgrid(yi, xi, indexing='ij')
            mean = mean(xxi, yyi) # replace function 'mean' by its evaluation on the grid
        else:
            mean = np.asarray(mean, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if mean.size == 1:
                if x is not None:
                    mean_x = mean
            elif mean.size == nxyz:
                mean = mean.reshape(ny, nx)
                if x is not None:
                    mean_x = img.Img_interp_func(img.Img(nx, ny, 1, sx, sy, 1., ox, oy, 0., nv=1, val=mean), iz=0)(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `mean` is not valid")
                return None

    # Check parameters - var
    var_x = var
    if var is not None:
        if method == 'ordinary_kriging':
            if verbose > 0:
                print(f"ERROR ({fname}): specifying `var` not allowed with ordinary kriging")
            return None
        if callable(var):
            if x is not None:
                var_x = var(x[:, 0], x[:, 1])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            yi = oy + sy*(0.5+np.arange(ny)) # y-coordinate of cell center
            yyi, xxi = np.meshgrid(yi, xi, indexing='ij')
            var = var(xxi, yyi) # replace function 'var' by its evaluation on the grid
        else:
            var = np.asarray(var, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if var.size == 1:
                if x is not None:
                    var_x = var
            elif var.size == nxyz:
                var = var.reshape(ny, nx)
                if x is not None:
                    var_x = img.Img_interp_func(img.Img(nx, ny, 1, sx, sy, 1., ox, oy, 0., nv=1, val=var), iz=0)(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `var` is not valid")
                return None

    # data points: x, v
    dataPointSet = []

    # data point set from x, v
    if x is not None:
        if aggregate_data_op == 'krige':
            if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model with non-stationary weight or range cannot be used with `aggregate_data_op`='{aggregate_data_op}'")
                return None
            if cov_model.is_orientation_stationary():
                cov_model_agg = cov_model
            else:
                cov_model_agg = gcm.copyCovModel(cov_model)
                cov_model_agg.set_alpha(0.0)
            # Get grid cell with at least one data point:
            # x_agg: 2D array, each row contains the coordinates of the center of such cell
            im_tmp = img.imageFromPoints(x, values=None, varname=None,
                                         nx=nx, ny=ny, sx=sx, sy=sy, ox=ox, oy=oy,
                                         indicator_var=True, count_var=False)
            ind_agg = np.where(im_tmp.val[0])
            if len(ind_agg[0]) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None
            x_agg = np.array((im_tmp.xx()[ind_agg].reshape(-1), im_tmp.yy()[ind_agg].reshape(-1))).T
            # x_agg = np.array((im_tmp.xx()[*ind_agg].reshape(-1), im_tmp.yy()[*ind_agg].reshape(-1))).T
            ind_agg = ind_agg[1:] # remove index along z axis
            del(im_tmp)
            # Compute kriging estimate (v_agg) and kriging std (v_agg_std) at x_agg
            if mean is not None and mean.size > 1:
                mean_x_agg = mean[ind_agg]
                # mean_x_agg = mean[*ind_agg]
            else:
                mean_x_agg = mean
            if var is not None and var.size > 1:
                var_x_agg = var[ind_agg]
                # var_x_agg = var[*ind_agg]
            else:
                var_x_agg = var
            if isinstance(cov_model.alpha, np.ndarray) and cov_model.alpha.size == nxyz:
                alpha_x_agg = cov_model.alpha.reshape(ny, nx)[ind_agg]
                # alpha_x_agg = cov_model.alpha.reshape(ny, nx)[*ind_agg]
            else:
                alpha_x_agg = cov_model.alpha
            # Set parameters `use_unique_neighborhood` and `nneighborMax`
            # from the arguments if not given in `aggregate_data_op_kwargs`
            if 'use_unique_neighborhood' not in aggregate_data_op_kwargs.keys():
                aggregate_data_op_kwargs['use_unique_neighborhood'] = use_unique_neighborhood
            if 'nneighborMax' not in aggregate_data_op_kwargs.keys():
                aggregate_data_op_kwargs['nneighborMax'] = nneighborMax
            try:
                v_agg, v_agg_std = gcm.krige(x, v, x_agg, cov_model_agg, method=method,
                                             mean_x=mean_x, mean_xu=mean_x_agg,
                                             var_x=var_x, var_xu=var_x_agg,
                                             alpha_xu=alpha_x_agg,
                                             verbose=0, **aggregate_data_op_kwargs)
            except:
                if verbose > 0:
                    print(f"ERROR ({fname}): kriging error")
                return None
            xx_agg, yy_agg = x_agg.T
            zz_agg = np.ones_like(xx_agg) * oz + 0.5 * sz
        else:
            # Aggregate data on grid cell by using the given operation
            xx, yy = x.T
            zz = np.ones_like(xx) * oz + 0.5 * sz
            try:
                xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                    xx, yy, zz, v,
                                                    nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                    op=aggregate_data_op, **aggregate_data_op_kwargs)
            except:
                if verbose > 0:
                    print(f"ERROR ({fname}): data aggregation (`aggregate_data_op='{aggregate_data_op}'`) failed")
                return None
            if len(xx_agg) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None

        dataPointSet.append(
            PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
            )

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # --- Fill mpds_geosClassicInput structure (C)
    mpds_geosClassicInput, flag = fill_mpds_geosClassicInput(
        space_dim,
        cov_model,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        outputReportFile,
        computationMode,
        None,
        dataPointSet,
        mask,
        mean,
        var,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        0,
        0,
        0,
        0)

    if not flag:
        if verbose > 0:
            print(f'ERROR ({fname}): can not fill input structure!')
        return None

    # --- Prepare mpds_geosClassicIOutput structure (C)
    # Allocate mpds_geosClassicOutput
    mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

    # Init mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

    # --- Set progress monitor
    mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
    geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

    # Set function to update progress monitor:
    # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
    # the function
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
    # should be used, but the following function can also be used:
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
    if verbose < 3:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
    else:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if verbose >= 2:
        print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

    # --- Launch "GeosClassicSim" (launch C code)
    # err = geosclassic.MPDSGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
    err = geosclassic.MPDSOMPGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

    # Free memory on C side: mpds_geosClassicInput
    geosclassic.MPDSGeosClassicFreeGeosClassicInput(mpds_geosClassicInput)
    #geosclassic.MPDSFree(mpds_geosClassicInput)
    geosclassic.free_MPDS_GEOSCLASSICINPUT(mpds_geosClassicInput)

    if err:
        if verbose > 0:
            err_message = geosclassic.mpds_get_error_message(-err)
            err_message = err_message.replace('\n', '')
            print(err_message)
        geosclassic_output = None
    else:
        geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

    # Free memory on C side: mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
    #geosclassic.MPDSFree(mpds_geosClassicOutput)
    geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

    # Free memory on C side: mpds_progressMonitor
    #geosclassic.MPDSFree(mpds_progressMonitor)
    geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    if geosclassic_output is not None and x is not None and aggregate_data_op == 'krige':
        # Set kriging standard deviation at grid cell containing a data
        geosclassic_output['image'].val[1, 0, ind_agg[0], ind_agg[1]] = v_agg_std
        # geosclassic_output['image'].val[1, 0, *ind_agg] = v_agg_std

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def estimate3D(
        cov_model,
        dimension, spacing=(1.0, 1.0, 1.0), origin=(0.0, 0.0, 0.0),
        method='simple_kriging',
        mean=None, var=None,
        x=None, v=None,
        aggregate_data_op=None,
        aggregate_data_op_kwargs=None,
        mask=None,
        add_data_point_to_mask=True,
        use_unique_neighborhood=False,
        searchRadiusRelative=1.0,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Computes kriging estimates and standard deviations in 3D.

    Interpolation takes place in (center of) grid cells, based on simple or
    ordinary kriging.

    Parameters
    ----------
    cov_model : :class:`geone.CovModel.CovModel3D`
        covariance model in 3D
    dimension : 3-tuple of ints
        `dimension=(nx, ny, nz)`, number of cells in the 3D simulation grid along
        each axis
    spacing : 3-tuple of floats, default: (1.0,1.0, 1.0)
        `spacing=(sx, sy, sz)`, cell size along each axis
    origin : 3-tuple of floats, default: (0.0, 0.0, 0.0)
        `origin=(ox, oy, oz)`, origin of the 3D simulation grid (bottom-lower-left
        corner)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    mean : function (callable), or array-like of floats, or float, optional
        kriging mean value:
        - if a function: function of three arguments (xi, yi, zi) that returns
        the mean at location (xi, yi, zi)
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), mean values at grid cells (for
        non-stationary mean)
        - if a float: same mean value at every grid cell
        - by default (`None`): the mean of data value (`v`) (0.0 if no data) is
        considered at every grid cell
    var : function (callable), or array-like of floats, or float, optional
        kriging variance value:
        - if a function: function of three arguments (xi, yi, yi) that returns
        the variance at location (xi, yi, zi)
        - if array-like: its size must be equal to the number of grid cells
        (the array is reshaped if needed), variance values at grid cells (for
        non-stationary variance)
        - if a float: same variance value at every grid cell
        - by default (`None`): not used (use of covariance model only)
    x : 2D array of floats of shape (n, 3), optional
        data points locations, with n the number of data points, each row of `x`
        is the float coordinates of one data point; note: if n=1, a 1D array of
        shape (3,) is accepted
    v : 1D array of floats of shape (n,), optional
        data values at `x` (`v[i]` is the data value at `x[i]`)
    aggregate_data_op : str {'krige', 'min', 'max', 'mean', 'quantile',
                        'most_freq', 'random'}, optional
        operation used to aggregate data points falling in the same grid cells;
        - if `aggregate_data_op='krige'`: function `geone.covModel.krige` is used
        with the covariance model `cov_model` given in arguments, as well as
        the parameters `use_unique_neighborhood`, `nneighborMax` given in
        arguments unless they are given in `aggregate_data_op_kwargs`
        - if `aggregate_data_op='most_freq'`: most frequent value is selected
        (smallest one if more than one value with the maximal frequence)
        - if `aggregate_data_op='random'`: value from a random point is selected
        - otherwise: the function `numpy.<aggregate_data_op>` is used with the
        additional parameters given by `aggregate_data_op_kwargs`, note that, e.g.
        `aggregate_data_op='quantile'` requires the additional parameter
        `q=<quantile_to_compute>`;
        by default: if covariance model has stationary ranges and weight (sill),
        `aggregate_data_op='krige'` is used, otherwise `aggregate_data_op='mean'`
    aggregate_data_op_kwargs : dict, optional
        keyword arguments to be passed to `geone.covModel.krige` or
        `numpy.<aggregate_data_op>`, according to the parameter
        `aggregate_data_op`
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    use_unique_neighborhood : bool, default: False
        indicates if a unique neighborhood is used:
        - if True: all data points are taken into account for computing
        estimates and standard deviations; in this case: parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode` are
        not used
        - if False: only data points within a search ellipsoid are taken into
        account for computing estimates and standard deviations (see parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode`)
    searchRadiusRelative : float, default: 1.0
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=2` variables (estimates and standard
            deviations);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'estimate3D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = dimension
    sx, sy, sz = spacing
    ox, oy, oz = origin

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 3

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # cov_model
    if isinstance(cov_model, gcm.CovModel1D):
        cov_model = gcm.covModel1D_to_covModel3D(cov_model) # convert model 1D in 3D
            # -> will not be modified cov_model at exit

    if not isinstance(cov_model, gcm.CovModel3D):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model` is not valid")
        return None

    for el in cov_model.elem:
        # weight
        w = el[1]['w']
        if np.size(w) != 1 and np.size(w) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): `cov_model`: weight ('w') not compatible with simulation grid")
            return None
        # ranges
        if 'r' in el[1].keys():
            for r in el[1]['r']:
                if np.size(r) != 1 and np.size(r) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): `cov_model`: range ('r') not compatible with simulation grid")
                    return None
        # additional parameter (s)
        if 's' in el[1].keys():
            s  = el[1]['s']
            if np.size(s) != 1 and np.size(s) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): `cov_model`: parameter ('s') not compatible with simulation grid")
                return None

    # alpha
    angle = cov_model.alpha
    if np.size(angle) != 1 and np.size(angle) != nxyz:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model`: angle (alpha) not compatible with simulation grid")
        return None

    # beta
    angle = cov_model.beta
    if np.size(angle) != 1 and np.size(angle) != nxyz:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model`: angle (beta) not compatible with simulation grid")
        return None

    # gamma
    angle = cov_model.gamma
    if np.size(angle) != 1 and np.size(angle) != nxyz:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model`: angle (gamma) not compatible with simulation grid")
        return None

    # aggregate_data_op (default)
    if aggregate_data_op is None:
        if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
            aggregate_data_op = 'mean'
        else:
            aggregate_data_op = 'krige'

    if aggregate_data_op_kwargs is None:
        aggregate_data_op_kwargs = {}

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 1
    elif method == 'ordinary_kriging':
        computationMode = 0
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # If unique neighborhood is used, set searchRadiusRelative to -1
    #    (and initialize nneighborMax, searchNeighborhoodSortMode (unused))
    if use_unique_neighborhood:
        searchRadiusRelative = -1.0
        nneighborMax = 1
        searchNeighborhoodSortMode = 0

    else:
       # Check parameters - searchRadiusRelative
       if searchRadiusRelative < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
           if verbose > 0:
               print(f"ERROR ({fname}): `searchRadiusRelative` too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
           return None

       # Check parameters - nneighborMax
       if nneighborMax != -1 and nneighborMax <= 0:
           if verbose > 0:
               print(f"ERROR ({fname}): `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
           return None

       # Check parameters - searchNeighborhoodSortMode
       if searchNeighborhoodSortMode is None:
           # set greatest possible value
           if cov_model.is_stationary():
               searchNeighborhoodSortMode = 2
           else:
               searchNeighborhoodSortMode = 1
       else:
           if searchNeighborhoodSortMode == 2:
               if not cov_model.is_stationary():
                   if verbose > 0:
                       print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                   return None

       # if searchNeighborhoodSortMode is None:
       #     # set greatest possible value
       #     if cov_model.is_stationary():
       #         searchNeighborhoodSortMode = 2
       #     elif cov_model.is_orientation_stationary() and cov_model.is_range_stationary():
       #         searchNeighborhoodSortMode = 1
       #     else:
       #         searchNeighborhoodSortMode = 0
       # else:
       #     if searchNeighborhoodSortMode == 2:
       #         if not cov_model.is_stationary():
       #             if verbose > 0:
       #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
       #             return None
       #     elif searchNeighborhoodSortMode == 1:
       #         if not cov_model.is_orientation_stationary() or not cov_model.is_range_stationary():
       #             if verbose > 0:
       #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
       #             return None

    # Preparation of data points
    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 3) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

    # Check parameters - mean
    mean_x = mean
    if mean is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying `mean` not allowed with ordinary kriging")
        #     return None
        if callable(mean):
            if x is not None:
                mean_x = mean(x[:, 0], x[:, 1], x[:, 2])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            yi = oy + sy*(0.5+np.arange(ny)) # y-coordinate of cell center
            zi = oz + sz*(0.5+np.arange(nz)) # z-coordinate of cell center
            zzi, yyi, xxi = np.meshgrid(zi, yi, xi, indexing='ij')
            mean = mean(xxi, yyi, zzi) # replace function 'mean' by its evaluation on the grid
        else:
            mean = np.asarray(mean, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if mean.size == 1:
                if x is not None:
                    mean_x = mean
            elif mean.size == nxyz:
                mean = mean.reshape(nz, ny, nx)
                if x is not None:
                    mean_x = img.Img_interp_func(img.Img(nx, ny, nz, sx, sy, sz, ox, oy, oz, nv=1, val=mean))(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `mean` is not valid")
                return None

    # Check parameters - var
    var_x = var
    if var is not None:
        if method == 'ordinary_kriging':
            if verbose > 0:
                print(f"ERROR ({fname}): specifying `var` not allowed with ordinary kriging")
            return None
        if callable(var):
            if x is not None:
                var_x = var(x[:, 0], x[:, 1], x[:, 2])
            xi = ox + sx*(0.5+np.arange(nx)) # x-coordinate of cell center
            yi = oy + sy*(0.5+np.arange(ny)) # y-coordinate of cell center
            zi = oz + sz*(0.5+np.arange(nz)) # z-coordinate of cell center
            zzi, yyi, xxi = np.meshgrid(zi, yi, xi, indexing='ij')
            var = var(xxi, yyi, zzi) # replace function 'var' by its evaluation on the grid
        else:
            var = np.asarray(var, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
            if var.size == 1:
                if x is not None:
                    var_x = var
            elif var.size == nxyz:
                var = var.reshape(nz, ny, nx)
                if x is not None:
                    var_x = img.Img_interp_func(img.Img(nx, ny, nz, sx, sy, sz, ox, oy, oz, nv=1, val=var))(x)
            else:
                if verbose > 0:
                    print(f"ERROR ({fname}): size of `var` is not valid")
                return None

    # data points: x, v
    dataPointSet = []

    # data point set from x, v
    if x is not None:
        if aggregate_data_op == 'krige':
            if not cov_model.is_weight_stationary() or not cov_model.is_range_stationary():
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model with non-stationary weight or range cannot be used with `aggregate_data_op`='{aggregate_data_op}'")
                return None
            if cov_model.is_orientation_stationary():
                cov_model_agg = cov_model
            else:
                cov_model_agg = gcm.copyCovModel(cov_model)
                cov_model_agg.set_alpha(0.0)
                cov_model_agg.set_beta(0.0)
                cov_model_agg.set_gamma(0.0)
            # Get grid cell with at least one data point:
            # x_agg: 2D array, each row contains the coordinates of the center of such cell
            im_tmp = img.imageFromPoints(x, values=None, varname=None,
                                         nx=nx, ny=ny, nz=nz, sx=sx, sy=sy, sz=sz, ox=ox, oy=oy, oz=oz,
                                         indicator_var=True, count_var=False)
            ind_agg = np.where(im_tmp.val[0])
            if len(ind_agg[0]) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None
            x_agg = np.array((im_tmp.xx()[ind_agg].reshape(-1), im_tmp.yy()[ind_agg].reshape(-1), im_tmp.zz()[ind_agg].reshape(-1))).T
            # x_agg = np.array((im_tmp.xx()[*ind_agg].reshape(-1), im_tmp.yy()[*ind_agg].reshape(-1), im_tmp.zz()[*ind_agg].reshape(-1))).T
            del(im_tmp)
            # Compute kriging estimate (v_agg) and kriging std (v_agg_std) at x_agg
            if mean is not None and mean.size > 1:
                mean_x_agg = mean[ind_agg]
                # mean_x_agg = mean[*ind_agg]
            else:
                mean_x_agg = mean
            if var is not None and var.size > 1:
                var_x_agg = var[ind_agg]
                # var_x_agg = var[*ind_agg]
            else:
                var_x_agg = var
            if isinstance(cov_model.alpha, np.ndarray) and cov_model.alpha.size == nxyz:
                alpha_x_agg = cov_model.alpha[ind_agg]
                # alpha_x_agg = cov_model.alpha[*ind_agg]
            else:
                alpha_x_agg = cov_model.alpha
            if isinstance(cov_model.beta, np.ndarray) and cov_model.beta.size == nxyz:
                beta_x_agg = cov_model.beta[ind_agg]
                # beta_x_agg = cov_model.beta[*ind_agg]
            else:
                beta_x_agg = cov_model.beta
            if isinstance(cov_model.gamma, np.ndarray) and cov_model.gamma.size == nxyz:
                gamma_x_agg = cov_model.gamma[ind_agg]
                # gamma_x_agg = cov_model.gamma[*ind_agg]
            else:
                gamma_x_agg = cov_model.gamma
            # Set parameters `use_unique_neighborhood` and `nneighborMax`
            # from the arguments if not given in `aggregate_data_op_kwargs`
            if 'use_unique_neighborhood' not in aggregate_data_op_kwargs.keys():
                aggregate_data_op_kwargs['use_unique_neighborhood'] = use_unique_neighborhood
            if 'nneighborMax' not in aggregate_data_op_kwargs.keys():
                aggregate_data_op_kwargs['nneighborMax'] = nneighborMax
            try:
                v_agg, v_agg_std = gcm.krige(x, v, x_agg, cov_model_agg, method=method,
                                             mean_x=mean_x, mean_xu=mean_x_agg,
                                             var_x=var_x, var_xu=var_x_agg,
                                             alpha_xu=alpha_x_agg, beta_xu=beta_x_agg, gamma_xu=gamma_x_agg,
                                             verbose=0, **aggregate_data_op_kwargs)
            except:
                if verbose > 0:
                    print(f"ERROR ({fname}): kriging error")
                return None
            xx_agg, yy_agg, zz_agg = x_agg.T
        else:
            # Aggregate data on grid cell by using the given operation
            xx, yy, zz = x.T
            try:
                xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                    xx, yy, zz, v,
                                                    nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                    op=aggregate_data_op, **aggregate_data_op_kwargs)
            except:
                if verbose > 0:
                    print(f"ERROR ({fname}): data aggregation (`aggregate_data_op='{aggregate_data_op}'`) failed")
                return None
            if len(xx_agg) == 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): no data point in grid")
                return None

        dataPointSet.append(
            PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
            )

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # --- Fill mpds_geosClassicInput structure (C)
    mpds_geosClassicInput, flag = fill_mpds_geosClassicInput(
        space_dim,
        cov_model,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        outputReportFile,
        computationMode,
        None,
        dataPointSet,
        mask,
        mean,
        var,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        0,
        0,
        0,
        0)

    if not flag:
        if verbose > 0:
            print(f'ERROR ({fname}): can not fill input structure!')
        return None

    # --- Prepare mpds_geosClassicIOutput structure (C)
    # Allocate mpds_geosClassicOutput
    mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

    # Init mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

    # --- Set progress monitor
    mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
    geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

    # Set function to update progress monitor:
    # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
    # the function
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
    # should be used, but the following function can also be used:
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
    if verbose < 3:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
    else:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if verbose >= 2:
        print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

    # --- Launch "GeosClassicSim" (launch C code)
    # err = geosclassic.MPDSGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
    err = geosclassic.MPDSOMPGeosClassicSim(mpds_geosClassicInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

    # Free memory on C side: mpds_geosClassicInput
    geosclassic.MPDSGeosClassicFreeGeosClassicInput(mpds_geosClassicInput)
    #geosclassic.MPDSFree(mpds_geosClassicInput)
    geosclassic.free_MPDS_GEOSCLASSICINPUT(mpds_geosClassicInput)

    if err:
        if verbose > 0:
            err_message = geosclassic.mpds_get_error_message(-err)
            err_message = err_message.replace('\n', '')
            print(err_message)
        geosclassic_output = None
    else:
        geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

    # Free memory on C side: mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
    #geosclassic.MPDSFree(mpds_geosClassicOutput)
    geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

    # Free memory on C side: mpds_progressMonitor
    #geosclassic.MPDSFree(mpds_progressMonitor)
    geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    if geosclassic_output is not None and x is not None and aggregate_data_op == 'krige':
        # Set kriging standard deviation at grid cell containing a data
        geosclassic_output['image'].val[1, ind_agg[0], ind_agg[1], ind_agg[2]] = v_agg_std
        # geosclassic_output['image'].val[1, *ind_agg] = v_agg_std

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def fill_mpds_geosClassicIndicatorInput(
        space_dim,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        ncategory,
        categoryValue,
        outputReportFile,
        computationMode,
        cov_model_for_category,
        dataImage,
        dataPointSet,
        mask,
        probability,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        seed,
        nreal):
    """
    Fills a mpds_geosClassicIndicatorInput C structure from given parameters.

    This function should not be called directly, it is used in other functions
    of this module.

    Parameters
    ----------
    space_dim : int
        space dimension (1, 2, or 3)
    nx, ny, nz : ints
        number of grid cells along each axis
    sx, sy, sz : floats
        cell size along each axis
    ox, oy, oz : floats
        origin of the grid (bottom-lower-left corner)
    varname : str
        variable name
    ncategory : int
        number of categories
    categoryValue : array-like
        category values
    outputReportFile : bool
        indicates if a report file is desired
    computationMode : int
        computation mode:
        - `computationMode=0`: estimation, ordinary kriging
        - `computationMode=1`: estimation, simple kriging
        - `computationMode=2`: simulation, ordinary kriging
        - `computationMode=3`: simulation, simple kriging
    cov_model : sequence of :class:`geone.CovModel.CovModel<d>D`
        covariance model for each category
    dataImage : sequence of :class:`geone.img.Img`, or None
        list of data image(s)
    dataPointSet : sequence of :class:`geone.img.PointSet`, or None
        list of data point set(s)
    mask : array-like, or None
        mask value in grid cells
    probability : sequence of floats, or sequence of array-like, or None
        probability (mean) for each category
    searchRadiusRelative : float
        searchRadiusRelative parameter
    nneighborMax : int
        nneighborMax parameter
    searchNeighborhoodSortMode : int
        searchNeighborhoodSortMode parameter
    seed : int
        seed parameter
    nreal : int
        nreal parameter

    Returns
    -------
    mpds_geosClassicIndicatorInput : (MPDS_GEOSCLASSICINDICATORINPUT *)
        geosclassicIndicator input in C, intended for "GeosClassicIndicatorSim"
        C program
    flag : bool
        indicates if the filling has succeeded (True) or failed (False)
    """
    fname = 'fill_mpds_geosClassicIndicatorInput'

    nxy = nx * ny
    nxyz = nxy * nz

    # Allocate mpds_geosClassicIndicatorInput
    mpds_geosClassicIndicatorInput = geosclassic.malloc_MPDS_GEOSCLASSICINDICATORINPUT()

    # Init mpds_geosClassicIndicatorInput
    geosclassic.MPDSGeosClassicInitGeosClassicIndicatorInput(mpds_geosClassicIndicatorInput)

    # mpds_geosClassicIndicatorInput.consoleAppFlag
    mpds_geosClassicIndicatorInput.consoleAppFlag = geosclassic.FALSE

    # mpds_geosClassicIndicatorInput.simGrid
    mpds_geosClassicIndicatorInput.simGrid = geosclassic.malloc_MPDS_GRID()

    mpds_geosClassicIndicatorInput.simGrid.nx = int(nx)
    mpds_geosClassicIndicatorInput.simGrid.ny = int(ny)
    mpds_geosClassicIndicatorInput.simGrid.nz = int(nz)

    mpds_geosClassicIndicatorInput.simGrid.sx = float(sx)
    mpds_geosClassicIndicatorInput.simGrid.sy = float(sy)
    mpds_geosClassicIndicatorInput.simGrid.sz = float(sz)

    mpds_geosClassicIndicatorInput.simGrid.ox = float(ox)
    mpds_geosClassicIndicatorInput.simGrid.oy = float(oy)
    mpds_geosClassicIndicatorInput.simGrid.oz = float(oz)

    mpds_geosClassicIndicatorInput.simGrid.nxy = nxy
    mpds_geosClassicIndicatorInput.simGrid.nxyz = nxyz

    # mpds_geosClassicIndicatorInput.varname
    geosclassic.mpds_allocate_and_set_geosClassicIndicatorInput_varname(mpds_geosClassicIndicatorInput, varname)

    # mpds_geosClassicIndicatorInput.ncategory
    mpds_geosClassicIndicatorInput.ncategory = ncategory

    # mpds_geosClassicIndicatorInput.categoryValue
    mpds_geosClassicIndicatorInput.categoryValue = geosclassic.new_real_array(ncategory)
    geosclassic.mpds_set_real_vector_from_array(mpds_geosClassicIndicatorInput.categoryValue, 0, np.asarray(categoryValue).reshape(-1))

    # mpds_geosClassicIndicatorInput.outputMode
    mpds_geosClassicIndicatorInput.outputMode = geosclassic.GEOS_CLASSIC_OUTPUT_NO_FILE

    # mpds_geosClassicIndicatorInput.outputReportFlag and mpds_geosClassicIndicatorInput.outputReportFileName
    if outputReportFile is not None:
        mpds_geosClassicIndicatorInput.outputReportFlag = geosclassic.TRUE
        geosclassic.mpds_allocate_and_set_geosClassicIndicatorInput_outputReportFileName(mpds_geosClassicIndicatorInput, outputReportFile)
    else:
        mpds_geosClassicIndicatorInput.outputReportFlag = geosclassic.FALSE

    # mpds_geosClassicIndicatorInput.computationMode
    mpds_geosClassicIndicatorInput.computationMode = int(computationMode)

    # mpds_geosClassicIndicatorInput.covModel
    mpds_geosClassicIndicatorInput.covModel = geosclassic.new_MPDS_COVMODEL_array(int(ncategory))
    for i, cov_model in enumerate(cov_model_for_category):
        cov_model_c = geosclassic.malloc_MPDS_COVMODEL()
        geosclassic.MPDSGeosClassicInitCovModel(cov_model_c)
        if space_dim==1:
            cov_model_c, flag = covModel1D_py2C(cov_model, nx, ny, nz, sx, sy, sz, ox, oy, oz)
        elif space_dim==2:
            cov_model_c, flag = covModel2D_py2C(cov_model, nx, ny, nz, sx, sy, sz, ox, oy, oz)
        elif space_dim==3:
            cov_model_c, flag = covModel3D_py2C(cov_model, nx, ny, nz, sx, sy, sz, ox, oy, oz)
        if flag:
            geosclassic.MPDS_COVMODEL_array_setitem(mpds_geosClassicIndicatorInput.covModel, i, cov_model_c)
            # geosclassic.free_MPDS_COVMODEL(cov_model_c)
        else:
            geosclassic.free_MPDS_COVMODEL(cov_model_c)
            return mpds_geosClassicIndicatorInput, False

    # mpds_geosClassicIndicatorInput.searchRadiusRelative
    mpds_geosClassicIndicatorInput.searchRadiusRelative = geosclassic.new_real_array(int(ncategory))
    geosclassic.mpds_set_real_vector_from_array(
        mpds_geosClassicIndicatorInput.searchRadiusRelative, 0,
        np.asarray(searchRadiusRelative).reshape(int(ncategory)))

    # mpds_geosClassicIndicatorInput.nneighborMax
    mpds_geosClassicIndicatorInput.nneighborMax = geosclassic.new_int_array(int(ncategory))
    geosclassic.mpds_set_int_vector_from_array(
        mpds_geosClassicIndicatorInput.nneighborMax, 0,
        np.asarray(nneighborMax).reshape(int(ncategory)))

    # mpds_geosClassicIndicatorInput.searchNeighborhoodSortMode
    mpds_geosClassicIndicatorInput.searchNeighborhoodSortMode = geosclassic.new_int_array(int(ncategory))
    geosclassic.mpds_set_int_vector_from_array(
        mpds_geosClassicIndicatorInput.searchNeighborhoodSortMode, 0,
        np.asarray(searchNeighborhoodSortMode).reshape(int(ncategory)))

    # mpds_geosClassicIndicatorInput.ndataImage and mpds_geosClassicIndicatorInput.dataImage
    if dataImage is None:
        mpds_geosClassicIndicatorInput.ndataImage = 0
    else:
        dataImage = np.asarray(dataImage).reshape(-1)
        n = len(dataImage)
        mpds_geosClassicIndicatorInput.ndataImage = n
        mpds_geosClassicIndicatorInput.dataImage = geosclassic.new_MPDS_IMAGE_array(n)
        for i, dataIm in enumerate(dataImage):
            im_c = img_py2C(dataIm)
            geosclassic.MPDS_IMAGE_array_setitem(mpds_geosClassicIndicatorInput.dataImage, i, im_c)
            # geosclassic.free_MPDS_IMAGE(im_c)
            #
            # geosclassic.MPDS_IMAGE_array_setitem(mpds_geosClassicIndicatorInput.dataImage, i, img_py2C(dataIm))

    # mpds_geosClassicIndicatorInput.ndataPointSet and mpds_geosClassicIndicatorInput.dataPointSet
    if dataPointSet is None:
        mpds_geosClassicIndicatorInput.ndataPointSet = 0
    else:
        dataPointSet = np.asarray(dataPointSet).reshape(-1)
        n = len(dataPointSet)
        mpds_geosClassicIndicatorInput.ndataPointSet = n
        mpds_geosClassicIndicatorInput.dataPointSet = geosclassic.new_MPDS_POINTSET_array(n)
        for i, dataPS in enumerate(dataPointSet):
            ps_c = ps_py2C(dataPS)
            geosclassic.MPDS_POINTSET_array_setitem(mpds_geosClassicIndicatorInput.dataPointSet, i, ps_c)
            # geosclassic.free_MPDS_POINTSET(ps_c)
            #
            # geosclassic.MPDS_POINTSET_array_setitem(mpds_geosClassicIndicatorInput.dataPointSet, i, ps_py2C(dataPS))

    # mpds_geosClassicIndicatorInput.maskImageFlag and mpds_geosClassicIndicatorInput.maskImage
    if mask is None:
        mpds_geosClassicIndicatorInput.maskImageFlag = geosclassic.FALSE
    else:
        mpds_geosClassicIndicatorInput.maskImageFlag = geosclassic.TRUE
        im = Img(nx=nx, ny=ny, nz=nz,
                 sx=sx, sy=sy, sz=sz,
                 ox=ox, oy=oy, oz=oz,
                 nv=1, val=mask)
        mpds_geosClassicIndicatorInput.maskImage = img_py2C(im)

    # mpds_geosClassicIndicatorInput.probabilityUsage, mpds_geosClassicIndicatorInput.probabilityValue, mpds_geosClassicIndicatorInput.probabilityImage
    if probability is None:
        mpds_geosClassicIndicatorInput.probabilityUsage = 0
    elif probability.size == ncategory:
        mpds_geosClassicIndicatorInput.probabilityUsage = 1
        # mpds_geosClassicIndicatorInput.probabilityValue
        mpds_geosClassicIndicatorInput.probabilityValue = geosclassic.new_real_array(int(ncategory))
        geosclassic.mpds_set_real_vector_from_array(
            mpds_geosClassicIndicatorInput.probabilityValue, 0,
            np.asarray(probability).reshape(int(ncategory)))
    elif probability.size == ncategory*nxyz:
        mpds_geosClassicIndicatorInput.probabilityUsage = 2
        im = Img(nx=nx, ny=ny, nz=nz,
                 sx=sx, sy=sy, sz=sz,
                 ox=ox, oy=oy, oz=oz,
                 nv=ncategory, val=probability)
        mpds_geosClassicIndicatorInput.probabilityImage = img_py2C(im)
    else:
        print(f"ERROR ({fname}): can not integrate `probability` (not compatible with simulation grid)")
        return mpds_geosClassicIndicatorInput, False

    # mpds_geosClassicIndicatorInput.seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    mpds_geosClassicIndicatorInput.seed = int(seed)

    # mpds_geosClassicIndicatorInput.seedIncrement
    mpds_geosClassicIndicatorInput.seedIncrement = 1

    # mpds_geosClassicIndicatorInput.nrealization
    mpds_geosClassicIndicatorInput.nrealization = int(nreal)

    return mpds_geosClassicIndicatorInput, True
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulateIndicator1D(
        category_values,
        cov_model_for_category,
        dimension, spacing=1.0, origin=0.0,
        method='simple_kriging',
        nreal=1,
        probability=None,
        x=None, v=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        seed=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Generates 1D simulations (Sequential Indicator Simulation, SIS).

    A simulation takes place in (center of) grid cells, based on simple or
    ordinary kriging of the indicator variables of the categories.

    Parameters
    ----------
    category_values : 1D array-like
        sequence of category values; let `ncategory` be the number of categories,
        then:
        - if `ncategory=1`: the unique category value given must not be equal to
        zero; it is used for a binary case with values "unique category value"
        and 0, where 0 indicates the absence of the considered medium; the
        conditioning data values should be equal to"unique category value" or 0
        - if `ncategory>=2`: it is used for a multi-category case with given
        category values (distinct); the conditioning data values should be in the
        `category_values`
    cov_model_for_category : [sequence of] :class:`geone.CovModel.CovModel1D`
        sequence of same length as `category_values` of covariance model in 1D,
        or a unique covariance model in 1D (recycled):
        covariance model for each category
    dimension : int
        `dimension=nx`, number of cells in the 1D simulation grid
    spacing : float, default: 1.0
        `spacing=sx`, cell size
    origin : float, default: 0.0
        `origin=ox`, origin of the 1D simulation grid (left border)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    nreal : int, default: 1
        number of realizations
    probability : array-like of floats, optional
        probability for each category:
        - sequence of same length as `category_values`:
        probability[i]: probability (proportion, kriging mean value for the
        indicator variable) for category `category_values[i]`, used for
        every grid cell
        - array-like of size ncategory * ngrid_cells, where ncategory is the
        length of `category_values` and ngrid_cells is the number of grid
        cells (the array is reshaped if needed): first ngrid_cells values are
        the probabilities (proportions, kriging mean values for the indicator
        variable) for the first category at grid cells, etc.
        (for non-stationary probailities / proportions);
        by default (`None`): proportion of each category computed from the
        data values (`v`) are used for every grid cell
        note: for ordinary kriging (`method='ordinary_kriging'`), it is used for
        case with no neighbor
    x : 1D array-like of floats, optional
        data points locations (float coordinates); note: if one point, a float
        is accepted
    v : 1D array-like of floats, optional
        data values at `x` (`v[i]` is the data value at `x[i]`), array of same
        length as `x` (or float if one point)
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    searchRadiusRelative : [sequence of] float(s), default: 1.0
        sequence of floats of same length as `category_values`, or
        a unique float (recycled); one parameter per category:
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    seed : int, optional
        seed for initializing random number generator
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicIndicatorSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=nreal` variables (simulations);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'simulateIndicator1D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = dimension, 1, 1
    sx, sy, sz = spacing, 1.0, 1.0
    ox, oy, oz = origin, 0.0, 0.0

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 1

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # category_values and ncategory (computed)
    try:
        category_values = np.asarray(category_values, dtype='float').reshape(-1)
    except:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is not valid")
        return None

    ncategory = len(category_values)
    if ncategory <= 0:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is empty")
        return None

    # cov_model_for_category
    cm_for_cat = cov_model_for_category # no need to work on a copy in 1D

    cm_for_cat = np.asarray(cm_for_cat).reshape(-1)
    if len(cm_for_cat) == 1:
        cm_for_cat = np.repeat(cm_for_cat, ncategory)
    elif len(cm_for_cat) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` of invalid length")
        return None
    if not np.all([isinstance(c, gcm.CovModel1D) for c in cm_for_cat]):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` should contains CovModel1D objects")
        return None

    for cov_model in cm_for_cat:
        for el in cov_model.elem:
            # weight
            w = el[1]['w']
            if np.size(w) != 1 and np.size(w) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model: weight ('w') not compatible with simulation grid")
                return None
            # ranges
            if 'r' in el[1].keys():
                r  = el[1]['r']
                if np.size(r) != 1 and np.size(r) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): covariance model: range ('r') not compatible with simulation grid")
                    return None
            # additional parameter (s)
            if 's' in el[1].keys():
                s  = el[1]['s']
                if np.size(s) != 1 and np.size(s) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): covariance model: parameter ('s') not compatible with simulation grid")
                    return None

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 3
    elif method == 'ordinary_kriging':
        computationMode = 2
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # data points: x, v
    dataPointSet = []

    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 1) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

        # Aggregate data on grid by taking the most frequent value in grid cell
        xx = x[:, 0]
        yy = np.ones_like(xx) * oy + 0.5 * sy
        zz = np.ones_like(xx) * oz + 0.5 * sz
        try:
            xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, v,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op='most_freq')
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): data aggregation ('most_freq') failed")
            return None
        if len(xx_agg) == 0:
            if verbose > 0:
                print(f"ERROR ({fname}): no data point in grid")
            return None

        dataPointSet.append(
            PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
            )

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # Check parameters - searchRadiusRelative
    searchRadiusRelative = np.asarray(searchRadiusRelative, dtype='float').reshape(-1)
    if len(searchRadiusRelative) == 1:
        searchRadiusRelative = np.repeat(searchRadiusRelative, ncategory)
    elif len(searchRadiusRelative) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchRadiusRelative` of invalid length")
        return None

    for srr in searchRadiusRelative:
        if srr < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
            if verbose > 0:
                print(f"ERROR ({fname}): a `searchRadiusRelative` is too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
            return None

    # Check parameters - nneighborMax
    nneighborMax = np.asarray(nneighborMax, dtype='intc').reshape(-1)
    if len(nneighborMax) == 1:
        nneighborMax = np.repeat(nneighborMax, ncategory)
    elif len(nneighborMax) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `nneighborMax` of invalid length")
        return None

    for nn in nneighborMax:
        if nn != -1 and nn <= 0:
            if verbose > 0:
                print(f"ERROR ({fname}): any `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
            return None

    # Check parameters - searchNeighborhoodSortMode
    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode).reshape(-1)
    if len(searchNeighborhoodSortMode) == 1:
        searchNeighborhoodSortMode = np.repeat(searchNeighborhoodSortMode, ncategory)
    elif len(searchNeighborhoodSortMode) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchNeighborhoodSortMode` of invalid length")
        return None

    for i in range(ncategory):
        if searchNeighborhoodSortMode[i] is None:
            # set greatest possible value
            if cm_for_cat[i].is_stationary():
                searchNeighborhoodSortMode[i] = 2
            else:
                searchNeighborhoodSortMode[i] = 1
        else:
            if searchNeighborhoodSortMode[i] == 2:
                if not cm_for_cat[i].is_stationary():
                    if verbose > 0:
                        print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                    return None

    # for i in range(ncategory):
    #     if searchNeighborhoodSortMode[i] is None:
    #         # set greatest possible value
    #         if cm_for_cat[i].is_stationary():
    #             searchNeighborhoodSortMode[i] = 2
    #         elif cm_for_cat[i].is_orientation_stationary() and cm_for_cat[i].is_range_stationary():
    #             searchNeighborhoodSortMode[i] = 1
    #         else:
    #             searchNeighborhoodSortMode[i] = 0
    #     else:
    #         if searchNeighborhoodSortMode[i] == 2:
    #             if not cm_for_cat[i].is_stationary():
    #                 if verbose > 0:
    #                     print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
    #                 return None
    #         elif searchNeighborhoodSortMode[i] == 1:
    #             if not cm_for_cat[i].is_orientation_stationary() or not cm_for_cat[i].is_range_stationary():
    #                 if verbose > 0:
    #                     print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
    #                 return None

    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode, dtype='intc')

    # Check parameters - probability
    if probability is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying 'probability' not allowed with ordinary kriging")
        #     return None
        probability = np.asarray(probability, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if probability.size not in (ncategory, ncategory*nxyz):
            if verbose > 0:
                print(f"ERROR ({fname}): size of `probability` is not valid")
            return None

    # Check parameters - nreal
    nreal = int(nreal) # cast to int if needed

    if nreal <= 0:
        if verbose >= 1:
            if verbose > 0:
                print(f'{fname}: nreal <= 0: nothing to do!')
        return None

    # --- Fill mpds_geosClassicInput structure (C)
    mpds_geosClassicIndicatorInput, flag = fill_mpds_geosClassicIndicatorInput(
        space_dim,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        ncategory,
        category_values,
        outputReportFile,
        computationMode,
        cm_for_cat,
        None,
        dataPointSet,
        mask,
        probability,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        seed,
        nreal)

    if not flag:
        if verbose > 0:
            print(f'ERROR ({fname}): can not fill input structure!')
        return None

    # --- Prepare mpds_geosClassicIOutput structure (C)
    # Allocate mpds_geosClassicOutput
    mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

    # Init mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

    # --- Set progress monitor
    mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
    geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

    # Set function to update progress monitor:
    # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
    # the function
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
    # should be used, but the following function can also be used:
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
    if verbose < 3:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
    else:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if verbose >= 2:
        print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

    # --- Launch "GeosClassicSim" (launch C code)
    # err = geosclassic.MPDSGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
    err = geosclassic.MPDSOMPGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

    # Free memory on C side: mpds_geosClassicIndicatorInput
    geosclassic.MPDSGeosClassicFreeGeosClassicIndicatorInput(mpds_geosClassicIndicatorInput)
    #geosclassic.MPDSFree(mpds_geosClassicIndicatorInput)
    geosclassic.free_MPDS_GEOSCLASSICINDICATORINPUT(mpds_geosClassicIndicatorInput)

    if err:
        if verbose > 0:
            err_message = geosclassic.mpds_get_error_message(-err)
            err_message = err_message.replace('\n', '')
            print(err_message)
        geosclassic_output = None
    else:
        geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

    # Free memory on C side: mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
    #geosclassic.MPDSFree(mpds_geosClassicOutput)
    geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

    # Free memory on C side: mpds_progressMonitor
    #geosclassic.MPDSFree(mpds_progressMonitor)
    geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulateIndicator1D_mp(
        category_values,
        cov_model_for_category,
        dimension, spacing=1.0, origin=0.0,
        method='simple_kriging',
        nreal=1,
        probability=None,
        x=None, v=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        seed=None,
        outputReportFile=None,
        treat_image_one_by_one=False,
        nproc=None, nthreads_per_proc=None,
        verbose=2):
    """
    Computes the same as the function `simulateIndicator1D`, using multiprocessing.

    All the parameters are the same as those of the function
    `simulateIndicator1D`, except `nthreads` that is replaced by the parameters
    `nproc` and `nthreads_per_proc`, and an extra parameter
    `treat_image_one_by_one`.

    This function launches multiple processes (based on `multiprocessing`
    package):
    - `nproc` parallel processes using each one `nthreads_per_proc` threads
    are launched [parallel calls of the function `simulateIndicator1D`];
    - the set of realizations (specified by `nreal`) is distributed in a
    balanced way over the processes;
    - in terms of resources, this implies the use of `nproc*nthreads_per_proc`
    cpu(s).

    Parameters
    ----------
    (new parameters)
    nproc : int, optional
        number of processes; by default (`None`):
        `nproc` is set to `min(nmax-1, nreal)` (but at least 1), where nmax is
        the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    nthreads_per_proc : int, optional
        number of thread(s) per process (should be > 0); by default (`None`):
        `nthreads_per_proc` is automatically computed as the maximal integer
        (but at least 1) such that `nproc*nthreads_per_proc <= nmax-1`, where
        nmax is the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    treat_image_one_by_one : bool, default: False
        keyword argument passed to the function `geone.img.gatherImages`:
        - if True: images (result of each process) are gathered one by one,
        i.e. the variables of each image are inserted in an output image one by
        one and removed from the source (slower, may save memory)
        - if False: images (result of each process) are gathered at once,
        i.e. the variables of all images are inserted in an output image at once,
        and then removed (faster)

    See function `simulateIndicator1D`.
    """
    # fname = 'simulateIndicator1D_mp'

    # Set number of processes: nproc
    if nproc is None:
        nproc = max(min(multiprocessing.cpu_count()-1, nreal), 1)
    else:
        nproc_tmp = nproc
        nproc = max(min(int(nproc), nreal), 1)
        if verbose > 0 and nproc != nproc_tmp:
            print('NOTE: number of processes has been changed (now: nproc={})'.format(nproc))

    # Set number of threads per process: nth
    if nthreads_per_proc is None:
        nth = max(int(np.floor((multiprocessing.cpu_count()-1) / nproc)), 1)
    else:
        nth = max(int(nthreads_per_proc), 1)
        if verbose > 0 and nth != nthreads_per_proc:
            print('NOTE: number of threads per process has been changed (now: nthreads_per_proc={})'.format(nth))

    if verbose > 0 and nproc * nth > multiprocessing.cpu_count():
        print('NOTE: total number of cpu(s) used will exceed number of cpu(s) of the system...')

    # Set the distribution of the realizations over the processes
    # Condider the Euclidean division of nreal by nproc:
    #     nreal = q * nproc + r, with 0 <= r < nproc
    # Then, (q+1) realizations will be done on process 0, 1, ..., r-1, and q realization on process r, ..., nproc-1
    # Define the list real_index_proc of length (nproc+1) such that
    #   real_index_proc[i], ..., real_index_proc[i+1] - 1 : are the realization indices run on process i
    q, r = np.divmod(nreal, nproc)
    real_index_proc = [i*q + min(i, r) for i in range(nproc+1)]

    if verbose >= 2:
        print('Geos-Classic running on {} process(es)... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(nproc, geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching geos-classic...

    # Prepare seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    seed = int(seed)

    outputReportFile_p = None

    # Set pool of nproc workers
    pool = multiprocessing.Pool(nproc)
    out_pool = []
    for i in range(nproc):
        # Adapt input for i-th process
        nreal_p = real_index_proc[i+1] - real_index_proc[i]
        seed_p = seed + real_index_proc[i]
        if outputReportFile is not None:
            outputReportFile_p = outputReportFile + f'.{i}'
        if i==0:
            verbose_p = min(verbose, 1) # allow to print error for process i
        else:
            verbose_p = 0
        # Launch geos-classic (i-th process)
        out_pool.append(
            pool.apply_async(simulateIndicator1D,
                args=(category_values,
                cov_model_for_category,
                dimension, spacing, origin,
                method,
                nreal_p,                     # nreal (adjusted)
                probability,
                x, v,
                mask,
                add_data_point_to_mask,
                searchRadiusRelative,
                nneighborMax,
                searchNeighborhoodSortMode,
                seed_p,                      # seed (adjusted)
                outputReportFile_p,          # outputReportFile (adjusted)
                nth,                         # nthreads
                verbose_p)                   # verbose (adjusted)
                )
            )

    # Properly end working process
    pool.close() # Prevents any more tasks from being submitted to the pool,
    pool.join()  # then, wait for the worker processes to exit.

    # Get result from each process
    geosclassic_output_proc = [p.get() for p in out_pool]

    if np.any([out is None for out in geosclassic_output_proc]):
        return None

    # Gather results from every process
    # image
    image = []
    for out in geosclassic_output_proc:
        if out['image'] is not None:
            image.append(out['image'])
            del(out['image'])
    if len(image) == 0:
        image = None
    # Gather images and adjust variable names
    all_image = img.gatherImages(image, keep_varname=True, rem_var_from_source=True, treat_image_one_by_one=treat_image_one_by_one)
    ndigit = geosclassic.MPDS_GEOS_CLASSIC_NB_DIGIT_FOR_REALIZATION_NUMBER
    for j in range(all_image.nv):
        all_image.varname[j] = all_image.varname[j][:-ndigit] + f'{j:0{ndigit}d}'

    # nwarning
    nwarning = np.sum([out['nwarning'] for out in geosclassic_output_proc])
    # warnings
    warnings = list(np.unique(np.hstack([out['warnings'] for out in geosclassic_output_proc])))

    geosclassic_output = {'image':all_image, 'nwarning':nwarning, 'warnings':warnings}

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete (all process(es))')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulateIndicator2D(
        category_values,
        cov_model_for_category,
        dimension, spacing=(1.0, 1.0), origin=(0.0, 0.0),
        method='simple_kriging',
        nreal=1,
        probability=None,
        x=None, v=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        seed=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Generates 2D simulations (Sequential Indicator Simulation, SIS).

    A simulation takes place in (center of) grid cells, based on simple or
    ordinary kriging of the indicator variables of the categories.

    Parameters
    ----------
    category_values : 1D array-like
        sequence of category values; let `ncategory` be the number of categories,
        then:
        - if `ncategory=1`: the unique category value given must not be equal to
        zero; it is used for a binary case with values "unique category value"
        and 0, where 0 indicates the absence of the considered medium; the
        conditioning data values should be equal to"unique category value" or 0
        - if `ncategory>=2`: it is used for a multi-category case with given
        category values (distinct); the conditioning data values should be in the
        `category_values`
    cov_model_for_category : [sequence of] :class:`geone.CovModel.CovModel2D`
        sequence of same length as `category_values` of covariance model in 2D,
        or a unique covariance model in 2D (recycled):
        covariance model for each category
    dimension : 2-tuple of ints
        `dimension=(nx, ny)`, number of cells in the 2D simulation grid along
        each axis
    spacing : 2-tuple of floats, default: (1.0, 1.0)
        `spacing=(sx, sy)`, cell size along each axis
    origin : 2-tuple of floats, default: (0.0, 0.0)
        `origin=(ox, oy)`, origin of the 2D simulation grid (lower-left corner)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    nreal : int, default: 1
        number of realizations
    probability : array-like of floats, optional
        probability for each category:
        - sequence of same length as `category_values`:
        probability[i]: probability (proportion, kriging mean value for the
        indicator variable) for category `category_values[i]`, used for
        every grid cell
        - array-like of size ncategory * ngrid_cells, where ncategory is the
        length of `category_values` and ngrid_cells is the number of grid
        cells (the array is reshaped if needed): first ngrid_cells values are
        the probabilities (proportions, kriging mean values for the indicator
        variable) for the first category at grid cells, etc.
        (for non-stationary probailities / proportions);
        by default (`None`): proportion of each category computed from the
        data values (`v`) are used for every grid cell
        note: for ordinary kriging (`method='ordinary_kriging'`), it is used for
        case with no neighbor
    x : 2D array of floats of shape (n, 2), optional
        data points locations, with n the number of data points, each row of `x`
        is the float coordinates of one data point; note: if n=1, a 1D array of
        shape (2,) is accepted
    v : 1D array of floats of shape (n,), optional
        data values at `x` (`v[i]` is the data value at `x[i]`)
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    searchRadiusRelative : [sequence of] float(s), default: 1.0
        sequence of floats of same length as `category_values`, or
        a unique float (recycled); one parameter per category:
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    seed : int, optional
        seed for initializing random number generator
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicIndicatorSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=nreal` variables (simulations);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'simulateIndicator2D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = *dimension, 1
    sx, sy, sz = *spacing, 1.0
    ox, oy, oz = *origin, 0.0

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 2

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # category_values and ncategory (computed)
    try:
        category_values = np.asarray(category_values, dtype='float').reshape(-1)
    except:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is not valid")
        return None

    ncategory = len(category_values)
    if ncategory <= 0:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is empty")
        return None

    # cov_model_for_category
    cov_model_for_category = np.asarray(cov_model_for_category).reshape(-1)
    if not np.all([isinstance(c, gcm.CovModel2D) for c in cov_model_for_category]):
        # cov model will be converted:
        #    as applying modification in an array is persistent at exit,
        #    work on a copy to ensure no modification of the initial entry
        cm_for_cat = copy.deepcopy(cov_model_for_category)
    else:
        cm_for_cat = cov_model_for_category

    cm_for_cat = np.asarray(cm_for_cat).reshape(-1)
    for i in range(len(cm_for_cat)):
        if isinstance(cm_for_cat[i], gcm.CovModel1D):
            cm_for_cat[i] = gcm.covModel1D_to_covModel2D(cm_for_cat[i]) # convert model 1D in 2D
    if len(cm_for_cat) == 1:
        cm_for_cat = np.repeat(cm_for_cat, ncategory)
    elif len(cm_for_cat) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` of invalid length")
        return None
    if not np.all([isinstance(c, gcm.CovModel2D) for c in cm_for_cat]):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` should contains CovModel2D objects")
        return None

    for cov_model in cm_for_cat:
        for el in cov_model.elem:
            # weight
            w = el[1]['w']
            if np.size(w) != 1 and np.size(w) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model: weight ('w') not compatible with simulation grid")
                return None
            # ranges
            if 'r' in el[1].keys():
                for r in el[1]['r']:
                    if np.size(r) != 1 and np.size(r) != nxyz:
                        if verbose > 0:
                            print(f"ERROR ({fname}): covariance model: range ('r') not compatible with simulation grid")
                        return None
            # additional parameter (s)
            if 's' in el[1].keys():
                s  = el[1]['s']
                if np.size(s) != 1 and np.size(s) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): covariance model: parameter ('s') not compatible with simulation grid")
                    return None

        # alpha
        angle = cov_model.alpha
        if np.size(angle) != 1 and np.size(angle) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): covariance model: angle (alpha) not compatible with simulation grid")
            return None

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 3
    elif method == 'ordinary_kriging':
        computationMode = 2
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # data points: x, v
    dataPointSet = []

    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 2) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

        # Aggregate data on grid by taking the most frequent value in grid cell
        xx, yy = x.T
        zz = np.ones_like(xx) * oz + 0.5 * sz
        try:
            xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, v,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op='most_freq')
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): data aggregation ('most_freq') failed")
            return None
        if len(xx_agg) == 0:
            if verbose > 0:
                print(f"ERROR ({fname}): no data point in grid")
            return None

        dataPointSet.append(
            PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
            )

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # Check parameters - searchRadiusRelative
    searchRadiusRelative = np.asarray(searchRadiusRelative, dtype='float').reshape(-1)
    if len(searchRadiusRelative) == 1:
        searchRadiusRelative = np.repeat(searchRadiusRelative, ncategory)
    elif len(searchRadiusRelative) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchRadiusRelative` of invalid length")
        return None

    for srr in searchRadiusRelative:
        if srr < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
            if verbose > 0:
                print(f"ERROR ({fname}): a `searchRadiusRelative` is too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
            return None

    # Check parameters - nneighborMax
    nneighborMax = np.asarray(nneighborMax, dtype='intc').reshape(-1)
    if len(nneighborMax) == 1:
        nneighborMax = np.repeat(nneighborMax, ncategory)
    elif len(nneighborMax) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `nneighborMax` of invalid length")
        return None

    for nn in nneighborMax:
        if nn != -1 and nn <= 0:
            if verbose > 0:
                print(f"ERROR ({fname}): any `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
            return None

    # Check parameters - searchNeighborhoodSortMode
    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode).reshape(-1)
    if len(searchNeighborhoodSortMode) == 1:
        searchNeighborhoodSortMode = np.repeat(searchNeighborhoodSortMode, ncategory)
    elif len(searchNeighborhoodSortMode) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchNeighborhoodSortMode` of invalid length")
        return None

    for i in range(ncategory):
        if searchNeighborhoodSortMode[i] is None:
            # set greatest possible value
            if cm_for_cat[i].is_stationary():
                searchNeighborhoodSortMode[i] = 2
            else:
                searchNeighborhoodSortMode[i] = 1
        else:
            if searchNeighborhoodSortMode[i] == 2:
                if not cm_for_cat[i].is_stationary():
                    if verbose > 0:
                        print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                    return None

    # for i in range(ncategory):
    #     if searchNeighborhoodSortMode[i] is None:
    #         # set greatest possible value
    #         if cm_for_cat[i].is_stationary():
    #             searchNeighborhoodSortMode[i] = 2
    #         elif cm_for_cat[i].is_orientation_stationary() and cm_for_cat[i].is_range_stationary():
    #             searchNeighborhoodSortMode[i] = 1
    #         else:
    #             searchNeighborhoodSortMode[i] = 0
    #     else:
    #         if searchNeighborhoodSortMode[i] == 2:
    #             if not cm_for_cat[i].is_stationary():
    #                 if verbose > 0:
    #                     print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
    #                 return None
    #         elif searchNeighborhoodSortMode[i] == 1:
    #             if not cm_for_cat[i].is_orientation_stationary() or not cm_for_cat[i].is_range_stationary():
    #                 if verbose > 0:
    #                     print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
    #                 return None

    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode, dtype='intc')

    # Check parameters - probability
    if probability is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying 'probability' not allowed with ordinary kriging")
        #     return None
        probability = np.asarray(probability, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if probability.size not in (ncategory, ncategory*nxyz):
            if verbose > 0:
                print(f"ERROR ({fname}): size of `probability` is not valid")
            return None

    # Check parameters - nreal
    nreal = int(nreal) # cast to int if needed

    if nreal <= 0:
        if verbose >= 2:
            print(f'{fname}: nreal <= 0: nothing to do!')
        return None

    # --- Fill mpds_geosClassicInput structure (C)
    mpds_geosClassicIndicatorInput, flag = fill_mpds_geosClassicIndicatorInput(
        space_dim,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        ncategory,
        category_values,
        outputReportFile,
        computationMode,
        cm_for_cat,
        None,
        dataPointSet,
        mask,
        probability,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        seed,
        nreal)

    if not flag:
        if verbose > 0:
            print(f'ERROR ({fname}): can not fill input structure!')
        return None

    # --- Prepare mpds_geosClassicIOutput structure (C)
    # Allocate mpds_geosClassicOutput
    mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

    # Init mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

    # --- Set progress monitor
    mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
    geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

    # Set function to update progress monitor:
    # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
    # the function
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
    # should be used, but the following function can also be used:
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
    if verbose < 3:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
    else:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if verbose >= 2:
        print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

    # --- Launch "GeosClassicSim" (launch C code)
    # err = geosclassic.MPDSGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
    err = geosclassic.MPDSOMPGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

    # Free memory on C side: mpds_geosClassicIndicatorInput
    geosclassic.MPDSGeosClassicFreeGeosClassicIndicatorInput(mpds_geosClassicIndicatorInput)
    #geosclassic.MPDSFree(mpds_geosClassicIndicatorInput)
    geosclassic.free_MPDS_GEOSCLASSICINDICATORINPUT(mpds_geosClassicIndicatorInput)

    if err:
        if verbose > 0:
            err_message = geosclassic.mpds_get_error_message(-err)
            err_message = err_message.replace('\n', '')
            print(err_message)
        geosclassic_output = None
    else:
        geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

    # Free memory on C side: mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
    #geosclassic.MPDSFree(mpds_geosClassicOutput)
    geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

    # Free memory on C side: mpds_progressMonitor
    #geosclassic.MPDSFree(mpds_progressMonitor)
    geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulateIndicator2D_mp(
        category_values,
        cov_model_for_category,
        dimension, spacing=(1.0, 1.0), origin=(0.0, 0.0),
        method='simple_kriging',
        nreal=1,
        probability=None,
        x=None, v=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        seed=None,
        outputReportFile=None,
        treat_image_one_by_one=False,
        nproc=None, nthreads_per_proc=None,
        verbose=2):
    """
    Computes the same as the function `simulateIndicator2D`, using multiprocessing.

    All the parameters are the same as those of the function
    `simulateIndicator2D`, except `nthreads` that is replaced by the parameters
    `nproc` and `nthreads_per_proc`, and an extra parameter
    `treat_image_one_by_one`.

    This function launches multiple processes (based on `multiprocessing`
    package):
    - `nproc` parallel processes using each one `nthreads_per_proc` threads
    are launched [parallel calls of the function `simulateIndicator2D`];
    - the set of realizations (specified by `nreal`) is distributed in a
    balanced way over the processes;
    - in terms of resources, this implies the use of `nproc*nthreads_per_proc`
    cpu(s).

    Parameters
    ----------
    (new parameters)
    nproc : int, optional
        number of processes; by default (`None`):
        `nproc` is set to `min(nmax-1, nreal)` (but at least 1), where nmax is
        the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    nthreads_per_proc : int, optional
        number of thread(s) per process (should be > 0); by default (`None`):
        `nthreads_per_proc` is automatically computed as the maximal integer
        (but at least 1) such that `nproc*nthreads_per_proc <= nmax-1`, where
        nmax is the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    treat_image_one_by_one : bool, default: False
        keyword argument passed to the function `geone.img.gatherImages`:
        - if True: images (result of each process) are gathered one by one,
        i.e. the variables of each image are inserted in an output image one by
        one and removed from the source (slower, may save memory)
        - if False: images (result of each process) are gathered at once,
        i.e. the variables of all images are inserted in an output image at once,
        and then removed (faster)

    See function `simulateIndicator2D`.
    """
    # fname = 'simulateIndicator2D_mp'

    # Set number of processes: nproc
    if nproc is None:
        nproc = max(min(multiprocessing.cpu_count()-1, nreal), 1)
    else:
        nproc_tmp = nproc
        nproc = max(min(int(nproc), nreal), 1)
        if verbose > 0 and nproc != nproc_tmp:
            print('NOTE: number of processes has been changed (now: nproc={})'.format(nproc))

    # Set number of threads per process: nth
    if nthreads_per_proc is None:
        nth = max(int(np.floor((multiprocessing.cpu_count()-1) / nproc)), 1)
    else:
        nth = max(int(nthreads_per_proc), 1)
        if verbose > 0 and nth != nthreads_per_proc:
            print('NOTE: number of threads per process has been changed (now: nthreads_per_proc={})'.format(nth))

    if verbose > 0 and nproc * nth > multiprocessing.cpu_count():
        print('NOTE: total number of cpu(s) used will exceed number of cpu(s) of the system...')

    # Set the distribution of the realizations over the processes
    # Condider the Euclidean division of nreal by nproc:
    #     nreal = q * nproc + r, with 0 <= r < nproc
    # Then, (q+1) realizations will be done on process 0, 1, ..., r-1, and q realization on process r, ..., nproc-1
    # Define the list real_index_proc of length (nproc+1) such that
    #   real_index_proc[i], ..., real_index_proc[i+1] - 1 : are the realization indices run on process i
    q, r = np.divmod(nreal, nproc)
    real_index_proc = [i*q + min(i, r) for i in range(nproc+1)]

    if verbose >= 2:
        print('Geos-Classic running on {} process(es)... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(nproc, geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching geos-classic...

    # Prepare seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    seed = int(seed)

    outputReportFile_p = None

    # Set pool of nproc workers
    pool = multiprocessing.Pool(nproc)
    out_pool = []
    for i in range(nproc):
        # Adapt input for i-th process
        nreal_p = real_index_proc[i+1] - real_index_proc[i]
        seed_p = seed + real_index_proc[i]
        if outputReportFile is not None:
            outputReportFile_p = outputReportFile + f'.{i}'
        if i==0:
            verbose_p = min(verbose, 1) # allow to print error for process i
        else:
            verbose_p = 0
        # Launch geos-classic (i-th process)
        out_pool.append(
            pool.apply_async(simulateIndicator2D,
                args=(category_values,
                cov_model_for_category,
                dimension, spacing, origin,
                method,
                nreal_p,                     # nreal (adjusted)
                probability,
                x, v,
                mask,
                add_data_point_to_mask,
                searchRadiusRelative,
                nneighborMax,
                searchNeighborhoodSortMode,
                seed_p,                      # seed (adjusted)
                outputReportFile_p,          # outputReportFile (adjusted)
                nth,                         # nthreads
                verbose_p)                   # verbose (adjusted)
                )
            )

    # Properly end working process
    pool.close() # Prevents any more tasks from being submitted to the pool,
    pool.join()  # then, wait for the worker processes to exit.

    # Get result from each process
    geosclassic_output_proc = [p.get() for p in out_pool]

    if np.any([out is None for out in geosclassic_output_proc]):
        return None

    # Gather results from every process
    # image
    image = []
    for out in geosclassic_output_proc:
        if out['image'] is not None:
            image.append(out['image'])
            del(out['image'])
    if len(image) == 0:
        image = None
    # Gather images and adjust variable names
    all_image = img.gatherImages(image, keep_varname=True, rem_var_from_source=True, treat_image_one_by_one=treat_image_one_by_one)
    ndigit = geosclassic.MPDS_GEOS_CLASSIC_NB_DIGIT_FOR_REALIZATION_NUMBER
    for j in range(all_image.nv):
        all_image.varname[j] = all_image.varname[j][:-ndigit] + f'{j:0{ndigit}d}'

    # nwarning
    nwarning = np.sum([out['nwarning'] for out in geosclassic_output_proc])
    # warnings
    warnings = list(np.unique(np.hstack([out['warnings'] for out in geosclassic_output_proc])))

    geosclassic_output = {'image':all_image, 'nwarning':nwarning, 'warnings':warnings}

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete (all process(es))')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulateIndicator3D(
        category_values,
        cov_model_for_category,
        dimension, spacing=(1.0, 1.0, 1.0), origin=(0.0, 0.0, 0.0),
        method='simple_kriging',
        nreal=1,
        probability=None,
        x=None, v=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        seed=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Generates 3D simulations (Sequential Indicator Simulation, SIS).

    A simulation takes place in (center of) grid cells, based on simple or
    ordinary kriging of the indicator variables of the categories.

    Parameters
    ----------
    category_values : 1D array-like
        sequence of category values; let `ncategory` be the number of categories,
        then:
        - if `ncategory=1`: the unique category value given must not be equal to
        zero; it is used for a binary case with values "unique category value"
        and 0, where 0 indicates the absence of the considered medium; the
        conditioning data values should be equal to "unique category value" or 0
        - if `ncategory>=2`: it is used for a multi-category case with given
        category values (distinct); the conditioning data values should be in the
        `category_values`
    cov_model_for_category : [sequence of] :class:`geone.CovModel.CovModel3D`
        sequence of same length as `category_values` of covariance model in 3D,
        or a unique covariance model in 3D (recycled):
        covariance model for each category
    dimension : 3-tuple of ints
        `dimension=(nx, ny, nz)`, number of cells in the 3D simulation grid along
        each axis
    spacing : 3-tuple of floats, default: (1.0,1.0, 1.0)
        `spacing=(sx, sy, sz)`, cell size along each axis
    origin : 3-tuple of floats, default: (0.0, 0.0, 0.0)
        `origin=(ox, oy, oz)`, origin of the 3D simulation grid (bottom-lower-left
        corner)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    nreal : int, default: 1
        number of realizations
    probability : array-like of floats, optional
        probability for each category:
        - sequence of same length as `category_values`:
        probability[i]: probability (proportion, kriging mean value for the
        indicator variable) for category `category_values[i]`, used for
        every grid cell
        - array-like of size ncategory * ngrid_cells, where ncategory is the
        length of `category_values` and ngrid_cells is the number of grid
        cells (the array is reshaped if needed): first ngrid_cells values are
        the probabilities (proportions, kriging mean values for the indicator
        variable) for the first category at grid cells, etc.
        (for non-stationary probailities / proportions);
        by default (`None`): proportion of each category computed from the
        data values (`v`) are used for every grid cell
        note: for ordinary kriging (`method='ordinary_kriging'`), it is used for
        case with no neighbor
    x : 2D array of floats of shape (n, 3), optional
        data points locations, with n the number of data points, each row of `x`
        is the float coordinates of one data point; note: if n=1, a 1D array of
        shape (3,) is accepted
    v : 1D array of floats of shape (n,), optional
        data values at `x` (`v[i]` is the data value at `x[i]`)
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    searchRadiusRelative : [sequence of] float(s), default: 1.0
        sequence of floats of same length as `category_values`, or
        a unique float (recycled); one parameter per category:
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    seed : int, optional
        seed for initializing random number generator
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicIndicatorSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=nreal` variables (simulations);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'simulateIndicator3D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = dimension
    sx, sy, sz = spacing
    ox, oy, oz = origin

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 3

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # category_values and ncategory (computed)
    try:
        category_values = np.asarray(category_values, dtype='float').reshape(-1)
    except:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is not valid")
        return None

    ncategory = len(category_values)
    if ncategory <= 0:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is empty")
        return None

    # cov_model_for_category
    cov_model_for_category = np.asarray(cov_model_for_category).reshape(-1)
    if not np.all([isinstance(c, gcm.CovModel3D) for c in cov_model_for_category]):
        # cov model will be converted:
        #    as applying modification in an array is persistent at exit,
        #    work on a copy to ensure no modification of the initial entry
        cm_for_cat = copy.deepcopy(cov_model_for_category)
    else:
        cm_for_cat = cov_model_for_category

    cm_for_cat = np.asarray(cm_for_cat).reshape(-1)
    for i in range(len(cm_for_cat)):
        if isinstance(cm_for_cat[i], gcm.CovModel1D):
            cm_for_cat[i] = gcm.covModel1D_to_covModel3D(cm_for_cat[i]) # convert model 1D in 3D
    if len(cm_for_cat) == 1:
        cm_for_cat = np.repeat(cm_for_cat, ncategory)
    elif len(cm_for_cat) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` of invalid length")
        return None
    if not np.all([isinstance(c, gcm.CovModel3D) for c in cm_for_cat]):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` should contains CovModel3D objects")
        return None

    for cov_model in cm_for_cat:
        for el in cov_model.elem:
            # weight
            w = el[1]['w']
            if np.size(w) != 1 and np.size(w) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model: weight ('w') not compatible with simulation grid")
                return None
            # ranges
            if 'r' in el[1].keys():
                for r in el[1]['r']:
                    if np.size(r) != 1 and np.size(r) != nxyz:
                        if verbose > 0:
                            print(f"ERROR ({fname}): covariance model: range ('r') not compatible with simulation grid")
                        return None
            # additional parameter (s)
            if 's' in el[1].keys():
                s  = el[1]['s']
                if np.size(s) != 1 and np.size(s) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): covariance model: parameter ('s') not compatible with simulation grid")
                    return None

        # alpha
        angle = cov_model.alpha
        if np.size(angle) != 1 and np.size(angle) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): covariance model: angle (alpha) not compatible with simulation grid")
            return None

        # beta
        angle = cov_model.beta
        if np.size(angle) != 1 and np.size(angle) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): covariance model: angle (beta) not compatible with simulation grid")
            return None

        # gamma
        angle = cov_model.gamma
        if np.size(angle) != 1 and np.size(angle) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): covariance model: angle (gamma) not compatible with simulation grid")
            return None

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 3
    elif method == 'ordinary_kriging':
        computationMode = 2
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # data points: x, v
    dataPointSet = []

    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 3) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

        # Aggregate data on grid by taking the most frequent value in grid cell
        xx, yy, zz = x.T
        try:
            xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, v,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op='most_freq')
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): data aggregation ('most_freq') failed")
            return None
        if len(xx_agg) == 0:
            if verbose > 0:
                print(f"ERROR ({fname}): no data point in grid")
            return None

        dataPointSet.append(
            PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
            )

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # Check parameters - searchRadiusRelative
    searchRadiusRelative = np.asarray(searchRadiusRelative, dtype='float').reshape(-1)
    if len(searchRadiusRelative) == 1:
        searchRadiusRelative = np.repeat(searchRadiusRelative, ncategory)
    elif len(searchRadiusRelative) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchRadiusRelative` of invalid length")
        return None

    for srr in searchRadiusRelative:
        if srr < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
            if verbose > 0:
                print(f"ERROR ({fname}): a `searchRadiusRelative` is too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
            return None

    # Check parameters - nneighborMax
    nneighborMax = np.asarray(nneighborMax, dtype='intc').reshape(-1)
    if len(nneighborMax) == 1:
        nneighborMax = np.repeat(nneighborMax, ncategory)
    elif len(nneighborMax) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `nneighborMax` of invalid length")
        return None

    for nn in nneighborMax:
        if nn != -1 and nn <= 0:
            if verbose > 0:
                print(f"ERROR ({fname}): any `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
            return None

    # Check parameters - searchNeighborhoodSortMode
    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode).reshape(-1)
    if len(searchNeighborhoodSortMode) == 1:
        searchNeighborhoodSortMode = np.repeat(searchNeighborhoodSortMode, ncategory)
    elif len(searchNeighborhoodSortMode) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchNeighborhoodSortMode` of invalid length")
        return None

    for i in range(ncategory):
        if searchNeighborhoodSortMode[i] is None:
            # set greatest possible value
            if cm_for_cat[i].is_stationary():
                searchNeighborhoodSortMode[i] = 2
            else:
                searchNeighborhoodSortMode[i] = 1
        else:
            if searchNeighborhoodSortMode[i] == 2:
                if not cm_for_cat[i].is_stationary():
                    if verbose > 0:
                        print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                    return None

    # for i in range(ncategory):
    #     if searchNeighborhoodSortMode[i] is None:
    #         # set greatest possible value
    #         if cm_for_cat[i].is_stationary():
    #             searchNeighborhoodSortMode[i] = 2
    #         elif cm_for_cat[i].is_orientation_stationary() and cm_for_cat[i].is_range_stationary():
    #             searchNeighborhoodSortMode[i] = 1
    #         else:
    #             searchNeighborhoodSortMode[i] = 0
    #     else:
    #         if searchNeighborhoodSortMode[i] == 2:
    #             if not cm_for_cat[i].is_stationary():
    #                 if verbose > 0:
    #                     print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
    #                 return None
    #         elif searchNeighborhoodSortMode[i] == 1:
    #             if not cm_for_cat[i].is_orientation_stationary() or not cm_for_cat[i].is_range_stationary():
    #                 if verbose > 0:
    #                     print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
    #                 return None

    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode, dtype='intc')

    # Check parameters - probability
    if probability is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying 'probability' not allowed with ordinary kriging")
        #     return None
        probability = np.asarray(probability, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if probability.size not in (ncategory, ncategory*nxyz):
            if verbose > 0:
                print(f"ERROR ({fname}): size of `probability` is not valid")
            return None

    # Check parameters - nreal
    nreal = int(nreal) # cast to int if needed

    if nreal <= 0:
        if verbose >= 2:
            print(f'{fname}: nreal <= 0: nothing to do!')
        return None

    # --- Fill mpds_geosClassicInput structure (C)
    mpds_geosClassicIndicatorInput, flag = fill_mpds_geosClassicIndicatorInput(
        space_dim,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        ncategory,
        category_values,
        outputReportFile,
        computationMode,
        cm_for_cat,
        None,
        dataPointSet,
        mask,
        probability,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        seed,
        nreal)

    if not flag:
        if verbose > 0:
            print(f'ERROR ({fname}): can not fill input structure!')
        return None

    # --- Prepare mpds_geosClassicIOutput structure (C)
    # Allocate mpds_geosClassicOutput
    mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

    # Init mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

    # --- Set progress monitor
    mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
    geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

    # Set function to update progress monitor:
    # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
    # the function
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
    # should be used, but the following function can also be used:
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
    if verbose < 3:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
    else:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if verbose >= 2:
        print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

    # --- Launch "GeosClassicSim" (launch C code)
    # err = geosclassic.MPDSGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
    err = geosclassic.MPDSOMPGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

    # Free memory on C side: mpds_geosClassicIndicatorInput
    geosclassic.MPDSGeosClassicFreeGeosClassicIndicatorInput(mpds_geosClassicIndicatorInput)
    #geosclassic.MPDSFree(mpds_geosClassicIndicatorInput)
    geosclassic.free_MPDS_GEOSCLASSICINDICATORINPUT(mpds_geosClassicIndicatorInput)

    if err:
        if verbose > 0:
            err_message = geosclassic.mpds_get_error_message(-err)
            err_message = err_message.replace('\n', '')
            print(err_message)
        geosclassic_output = None
    else:
        geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

    # Free memory on C side: mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
    #geosclassic.MPDSFree(mpds_geosClassicOutput)
    geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

    # Free memory on C side: mpds_progressMonitor
    #geosclassic.MPDSFree(mpds_progressMonitor)
    geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def simulateIndicator3D_mp(
        category_values,
        cov_model_for_category,
        dimension, spacing=(1.0, 1.0, 1.0), origin=(0.0, 0.0, 0.0),
        method='simple_kriging',
        nreal=1,
        probability=None,
        x=None, v=None,
        mask=None,
        add_data_point_to_mask=True,
        searchRadiusRelative=1.,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        seed=None,
        outputReportFile=None,
        treat_image_one_by_one=False,
        nproc=None, nthreads_per_proc=None,
        verbose=2):
    """
    Computes the same as the function `simulateIndicator3D`, using multiprocessing.

    All the parameters are the same as those of the function
    `simulateIndicator3D`, except `nthreads` that is replaced by the parameters
    `nproc` and `nthreads_per_proc`, and an extra parameter
    `treat_image_one_by_one`.

    This function launches multiple processes (based on `multiprocessing`
    package):
    - `nproc` parallel processes using each one `nthreads_per_proc` threads
    are launched [parallel calls of the function `simulateIndicator3D`];
    - the set of realizations (specified by `nreal`) is distributed in a
    balanced way over the processes;
    - in terms of resources, this implies the use of `nproc*nthreads_per_proc`
    cpu(s).

    Parameters
    ----------
    (new parameters)
    nproc : int, optional
        number of processes; by default (`None`):
        `nproc` is set to `min(nmax-1, nreal)` (but at least 1), where nmax is
        the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    nthreads_per_proc : int, optional
        number of thread(s) per process (should be > 0); by default (`None`):
        `nthreads_per_proc` is automatically computed as the maximal integer
        (but at least 1) such that `nproc*nthreads_per_proc <= nmax-1`, where
        nmax is the total number of cpu(s) of the system (retrieved by
        `multiprocessing.cpu_count()`)
    treat_image_one_by_one : bool, default: False
        keyword argument passed to the function `geone.img.gatherImages`:
        - if True: images (result of each process) are gathered one by one,
        i.e. the variables of each image are inserted in an output image one by
        one and removed from the source (slower, may save memory)
        - if False: images (result of each process) are gathered at once,
        i.e. the variables of all images are inserted in an output image at once,
        and then removed (faster)

    See function `simulateIndicator3D`.
    """
    # fname = 'simulateIndicator3D_mp'

    # Set number of processes: nproc
    if nproc is None:
        nproc = max(min(multiprocessing.cpu_count()-1, nreal), 1)
    else:
        nproc_tmp = nproc
        nproc = max(min(int(nproc), nreal), 1)
        if verbose > 0 and nproc != nproc_tmp:
            print('NOTE: number of processes has been changed (now: nproc={})'.format(nproc))

    # Set number of threads per process: nth
    if nthreads_per_proc is None:
        nth = max(int(np.floor((multiprocessing.cpu_count()-1) / nproc)), 1)
    else:
        nth = max(int(nthreads_per_proc), 1)
        if verbose > 0 and nth != nthreads_per_proc:
            print('NOTE: number of threads per process has been changed (now: nthreads_per_proc={})'.format(nth))

    if verbose > 0 and nproc * nth > multiprocessing.cpu_count():
        print('NOTE: total number of cpu(s) used will exceed number of cpu(s) of the system...')

    # Set the distribution of the realizations over the processes
    # Condider the Euclidean division of nreal by nproc:
    #     nreal = q * nproc + r, with 0 <= r < nproc
    # Then, (q+1) realizations will be done on process 0, 1, ..., r-1, and q realization on process r, ..., nproc-1
    # Define the list real_index_proc of length (nproc+1) such that
    #   real_index_proc[i], ..., real_index_proc[i+1] - 1 : are the realization indices run on process i
    q, r = np.divmod(nreal, nproc)
    real_index_proc = [i*q + min(i, r) for i in range(nproc+1)]

    if verbose >= 2:
        print('Geos-Classic running on {} process(es)... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(nproc, geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching geos-classic...

    # Prepare seed
    if seed is None:
        seed = np.random.randint(1, 1000000)
    seed = int(seed)

    outputReportFile_p = None

    # Set pool of nproc workers
    pool = multiprocessing.Pool(nproc)
    out_pool = []
    for i in range(nproc):
        # Adapt input for i-th process
        nreal_p = real_index_proc[i+1] - real_index_proc[i]
        seed_p = seed + real_index_proc[i]
        if outputReportFile is not None:
            outputReportFile_p = outputReportFile + f'.{i}'
        if i==0:
            verbose_p = min(verbose, 1) # allow to print error for process i
        else:
            verbose_p = 0
        # Launch geos-classic (i-th process)
        out_pool.append(
            pool.apply_async(simulateIndicator3D,
                args=(category_values,
                cov_model_for_category,
                dimension, spacing, origin,
                method,
                nreal_p,                     # nreal (adjusted)
                probability,
                x, v,
                mask,
                add_data_point_to_mask,
                searchRadiusRelative,
                nneighborMax,
                searchNeighborhoodSortMode,
                seed_p,                      # seed (adjusted)
                outputReportFile_p,          # outputReportFile (adjusted)
                nth,                         # nthreads
                verbose_p)                   # verbose (adjusted)
                )
            )

    # Properly end working process
    pool.close() # Prevents any more tasks from being submitted to the pool,
    pool.join()  # then, wait for the worker processes to exit.

    # Get result from each process
    geosclassic_output_proc = [p.get() for p in out_pool]

    if np.any([out is None for out in geosclassic_output_proc]):
        return None

    # Gather results from every process
    # image
    image = []
    for out in geosclassic_output_proc:
        if out['image'] is not None:
            image.append(out['image'])
            del(out['image'])
    if len(image) == 0:
        image = None
    # Gather images and adjust variable names
    all_image = img.gatherImages(image, keep_varname=True, rem_var_from_source=True, treat_image_one_by_one=treat_image_one_by_one)
    ndigit = geosclassic.MPDS_GEOS_CLASSIC_NB_DIGIT_FOR_REALIZATION_NUMBER
    for j in range(all_image.nv):
        all_image.varname[j] = all_image.varname[j][:-ndigit] + f'{j:0{ndigit}d}'

    # nwarning
    nwarning = np.sum([out['nwarning'] for out in geosclassic_output_proc])
    # warnings
    warnings = list(np.unique(np.hstack([out['warnings'] for out in geosclassic_output_proc])))

    geosclassic_output = {'image':all_image, 'nwarning':nwarning, 'warnings':warnings}

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete (all process(es))')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def estimateIndicator1D(
        category_values,
        cov_model_for_category,
        dimension, spacing=1.0, origin=0.0,
        method='simple_kriging',
        probability=None,
        x=None, v=None,
        mask=None,
        add_data_point_to_mask=True,
        use_unique_neighborhood=False,
        searchRadiusRelative=1.,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Computes estimate probabilities / proportions of categories (indicators) in 1D.
    based on simple or ordinary kriging.

    Interpolation (of the indicator variable of each category) takes place in
    (center of) grid cells, based on simple or ordinary kriging.

    Parameters
    ----------
    category_values : 1D array-like
        sequence of category values; let `ncategory` be the number of categories,
        then:
        - if `ncategory=1`: the unique category value given must not be equal to
        zero; it is used for a binary case with values "unique category value"
        and 0, where 0 indicates the absence of the considered medium; the
        conditioning data values should be equal to"unique category value" or 0
        - if `ncategory>=2`: it is used for a multi-category case with given
        category values (distinct); the conditioning data values should be in the
        `category_values`
    cov_model_for_category : [sequence of] :class:`geone.CovModel.CovModel1D`
        sequence of same length as `category_values` of covariance model in 1D,
        or a unique covariance model in 1D (recycled):
        covariance model for each category
    dimension : int
        `dimension=nx`, number of cells in the 1D simulation grid
    spacing : float, default: 1.0
        `spacing=sx`, cell size
    origin : float, default: 0.0
        `origin=ox`, origin of the 1D simulation grid (left border)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    probability : array-like of floats, optional
        probability for each category:
        - sequence of same length as `category_values`:
        probability[i]: probability (proportion, kriging mean value for the
        indicator variable) for category `category_values[i]`, used for
        every grid cell
        - array-like of size ncategory * ngrid_cells, where ncategory is the
        length of `category_values` and ngrid_cells is the number of grid
        cells (the array is reshaped if needed): first ngrid_cells values are
        the probabilities (proportions, kriging mean values for the indicator
        variable) for the first category at grid cells, etc.
        (for non-stationary probailities / proportions);
        by default (`None`): proportion of each category computed from the
        data values (`v`) are used for every grid cell
        note: for ordinary kriging (`method='ordinary_kriging'`), it is used for
        case with no neighbor
    x : 1D array-like of floats, optional
        data points locations (float coordinates); note: if one point, a float
        is accepted
    v : 1D array-like of floats, optional
        data values at `x` (`v[i]` is the data value at `x[i]`), array of same
        length as `x` (or float if one point)
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    use_unique_neighborhood : bool, default: False
        indicates if a unique neighborhood is used:
        - if True: all data points are taken into account for computing
        estimates and standard deviations; in this case: parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode` are
        not used
        - if False: only data points within a search ellipsoid are taken into
        account for computing estimates and standard deviations (see parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode`)
    searchRadiusRelative : [sequence of] float(s), default: 1.0
        sequence of floats of same length as `category_values`, or
        a unique float (recycled); one parameter per category:
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicIndicatorSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=ncategory` variables (probability /
            proportion estimates, of each category);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'estimateIndicator1D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = dimension, 1, 1
    sx, sy, sz = spacing, 1.0, 1.0
    ox, oy, oz = origin, 0.0, 0.0

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 1

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # category_values and ncategory (computed)
    try:
        category_values = np.asarray(category_values, dtype='float').reshape(-1)
    except:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is not valid")
        return None

    ncategory = len(category_values)
    if ncategory <= 0:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is empty")
        return None

    # cov_model_for_category
    cm_for_cat = cov_model_for_category # no need to work on a copy in 1D

    cm_for_cat = np.asarray(cm_for_cat).reshape(-1)
    if len(cm_for_cat) == 1:
        cm_for_cat = np.repeat(cm_for_cat, ncategory)
    elif len(cm_for_cat) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` of invalid length")
        return None
    if not np.all([isinstance(c, gcm.CovModel1D) for c in cm_for_cat]):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` should contains CovModel1D objects")
        return None

    for cov_model in cm_for_cat:
        for el in cov_model.elem:
            # weight
            w = el[1]['w']
            if np.size(w) != 1 and np.size(w) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model: weight ('w') not compatible with simulation grid")
                return None
            # ranges
            if 'r' in el[1].keys():
                r  = el[1]['r']
                if np.size(r) != 1 and np.size(r) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): covariance model: range ('r') not compatible with simulation grid")
                    return None
            # additional parameter (s)
            if 's' in el[1].keys():
                s  = el[1]['s']
                if np.size(s) != 1 and np.size(s) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): covariance model: parameter ('s') not compatible with simulation grid")
                    return None

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 1
    elif method == 'ordinary_kriging':
        computationMode = 0
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # data points: x, v
    dataPointSet = []

    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 1) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

        # Aggregate data on grid by taking the most frequent value in grid cell
        xx = x[:, 0]
        yy = np.ones_like(xx) * oy + 0.5 * sy
        zz = np.ones_like(xx) * oz + 0.5 * sz
        try:
            xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, v,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op='most_freq')
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): data aggregation ('most_freq') failed")
            return None
        if len(xx_agg) == 0:
            if verbose > 0:
                print(f"ERROR ({fname}): no data point in grid")
            return None

        dataPointSet.append(
            PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
            )

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # Check parameters - use_unique_neighborhood (length)
    use_unique_neighborhood = np.asarray(use_unique_neighborhood, dtype='bool').reshape(-1)
    if len(use_unique_neighborhood) == 1:
        use_unique_neighborhood = np.repeat(use_unique_neighborhood, ncategory)
    elif len(use_unique_neighborhood) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `use_unique_neighborhood` of invalid length")
        return None

    # Check parameters - searchRadiusRelative (length)
    searchRadiusRelative = np.asarray(searchRadiusRelative, dtype='float').reshape(-1)
    if len(searchRadiusRelative) == 1:
        searchRadiusRelative = np.repeat(searchRadiusRelative, ncategory)
    elif len(searchRadiusRelative) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchRadiusRelative` of invalid length")
        return None

    # Check parameters - nneighborMax (length)
    nneighborMax = np.asarray(nneighborMax, dtype='intc').reshape(-1)
    if len(nneighborMax) == 1:
        nneighborMax = np.repeat(nneighborMax, ncategory)
    elif len(nneighborMax) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `nneighborMax` of invalid length")
        return None

    # Check parameters - searchNeighborhoodSortMode (length)
    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode).reshape(-1)
    if len(searchNeighborhoodSortMode) == 1:
        searchNeighborhoodSortMode = np.repeat(searchNeighborhoodSortMode, ncategory)
    elif len(searchNeighborhoodSortMode) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchNeighborhoodSortMode` of invalid length")
        return None

    # If unique neighborhood is used, set searchRadiusRelative to -1
    #    (and initialize nneighborMax, searchNeighborhoodSortMode (unused))
    # else: check the parameters
    for i in range(ncategory):
        if use_unique_neighborhood[i]:
            searchRadiusRelative[i] = -1.0
            nneighborMax[i] = 1
            searchNeighborhoodSortMode[i] = 0

        else:
            if searchRadiusRelative[i] < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
                if verbose > 0:
                    print(f"ERROR ({fname}): a `searchRadiusRelative` is too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
                return None

            if nneighborMax[i] != -1 and nneighborMax[i] <= 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): any `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
                return None

            if searchNeighborhoodSortMode[i] is None:
                # set greatest possible value
                if cm_for_cat[i].is_stationary():
                    searchNeighborhoodSortMode[i] = 2
                else:
                    searchNeighborhoodSortMode[i] = 1
            else:
                if searchNeighborhoodSortMode[i] == 2:
                    if not cm_for_cat[i].is_stationary():
                        if verbose > 0:
                            print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                        return None

            # if searchNeighborhoodSortMode[i] is None:
            #     # set greatest possible value
            #     if cm_for_cat[i].is_stationary():
            #         searchNeighborhoodSortMode[i] = 2
            #     elif cm_for_cat[i].is_orientation_stationary() and cm_for_cat[i].is_range_stationary():
            #         searchNeighborhoodSortMode[i] = 1
            #     else:
            #         searchNeighborhoodSortMode[i] = 0
            # else:
            #     if searchNeighborhoodSortMode[i] == 2:
            #         if not cm_for_cat[i].is_stationary():
            #             if verbose > 0:
            #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
            #             return None
            #     elif searchNeighborhoodSortMode[i] == 1:
            #         if not cm_for_cat[i].is_orientation_stationary() or not cm_for_cat[i].is_range_stationary():
            #             if verbose > 0:
            #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
            #             return None

    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode, dtype='intc')

    # Check parameters - probability
    if probability is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying 'probability' not allowed with ordinary kriging")
        #     return None
        probability = np.asarray(probability, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if probability.size not in (ncategory, ncategory*nxyz):
            if verbose > 0:
                print(f"ERROR ({fname}): size of `probability` is not valid")
            return None

    # --- Fill mpds_geosClassicInput structure (C)
    mpds_geosClassicIndicatorInput, flag = fill_mpds_geosClassicIndicatorInput(
        space_dim,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        ncategory,
        category_values,
        outputReportFile,
        computationMode,
        cm_for_cat,
        None,
        dataPointSet,
        mask,
        probability,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        0,
        0)

    if not flag:
        if verbose > 0:
            print(f'ERROR ({fname}): can not fill input structure!')
        return None

    # --- Prepare mpds_geosClassicIOutput structure (C)
    # Allocate mpds_geosClassicOutput
    mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

    # Init mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

    # --- Set progress monitor
    mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
    geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

    # Set function to update progress monitor:
    # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
    # the function
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
    # should be used, but the following function can also be used:
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
    if verbose < 3:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
    else:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if verbose >= 2:
        print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

    # --- Launch "GeosClassicSim" (launch C code)
    # err = geosclassic.MPDSGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
    err = geosclassic.MPDSOMPGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

    # Free memory on C side: mpds_geosClassicIndicatorInput
    geosclassic.MPDSGeosClassicFreeGeosClassicIndicatorInput(mpds_geosClassicIndicatorInput)
    #geosclassic.MPDSFree(mpds_geosClassicIndicatorInput)
    geosclassic.free_MPDS_GEOSCLASSICINDICATORINPUT(mpds_geosClassicIndicatorInput)

    if err:
        if verbose > 0:
            err_message = geosclassic.mpds_get_error_message(-err)
            err_message = err_message.replace('\n', '')
            print(err_message)
        geosclassic_output = None
    else:
        geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

    # Free memory on C side: mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
    #geosclassic.MPDSFree(mpds_geosClassicOutput)
    geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

    # Free memory on C side: mpds_progressMonitor
    #geosclassic.MPDSFree(mpds_progressMonitor)
    geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def estimateIndicator2D(
        category_values,
        cov_model_for_category,
        dimension, spacing=(1.0, 1.0), origin=(0.0, 0.0),
        method='simple_kriging',
        probability=None,
        x=None, v=None,
        mask=None,
        add_data_point_to_mask=True,
        use_unique_neighborhood=False,
        searchRadiusRelative=1.,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Computes estimate probabilities / proportions of categories (indicators) in 2D.
    based on simple or ordinary kriging.

    Interpolation (of the indicator variable of each category) takes place in
    (center of) grid cells, based on simple or ordinary kriging.

    Parameters
    ----------
    category_values : 1D array-like
        sequence of category values; let `ncategory` be the number of categories,
        then:
        - if `ncategory=1`: the unique category value given must not be equal to
        zero; it is used for a binary case with values "unique category value"
        and 0, where 0 indicates the absence of the considered medium; the
        conditioning data values should be equal to"unique category value" or 0
        - if `ncategory>=2`: it is used for a multi-category case with given
        category values (distinct); the conditioning data values should be in the
        `category_values`
    cov_model_for_category : [sequence of] :class:`geone.CovModel.CovModel2D`
        sequence of same length as `category_values` of covariance model in 2D,
        or a unique covariance model in 2D (recycled):
        covariance model for each category
    dimension : 2-tuple of ints
        `dimension=(nx, ny)`, number of cells in the 2D simulation grid along
        each axis
    spacing : 2-tuple of floats, default: (1.0, 1.0)
        `spacing=(sx, sy)`, cell size along each axis
    origin : 2-tuple of floats, default: (0.0, 0.0)
        `origin=(ox, oy)`, origin of the 2D simulation grid (lower-left corner)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    probability : array-like of floats, optional
        probability for each category:
        - sequence of same length as `category_values`:
        probability[i]: probability (proportion, kriging mean value for the
        indicator variable) for category `category_values[i]`, used for
        every grid cell
        - array-like of size ncategory * ngrid_cells, where ncategory is the
        length of `category_values` and ngrid_cells is the number of grid
        cells (the array is reshaped if needed): first ngrid_cells values are
        the probabilities (proportions, kriging mean values for the indicator
        variable) for the first category at grid cells, etc.
        (for non-stationary probailities / proportions)
        by default (`None`): proportion of each category computed from the
        data values (`v`) are used for every grid cell;
        note: for ordinary kriging (`method='ordinary_kriging'`), it is used for
        case with no neighbor
    x : 2D array of floats of shape (n, 2), optional
        data points locations, with n the number of data points, each row of `x`
        is the float coordinates of one data point; note: if n=1, a 1D array of
        shape (2,) is accepted
    v : 1D array of floats of shape (n,), optional
        data values at `x` (`v[i]` is the data value at `x[i]`)
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    use_unique_neighborhood : bool, default: False
        indicates if a unique neighborhood is used:
        - if True: all data points are taken into account for computing
        estimates and standard deviations; in this case: parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode` are
        not used
        - if False: only data points within a search ellipsoid are taken into
        account for computing estimates and standard deviations (see parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode`)
    searchRadiusRelative : [sequence of] float(s), default: 1.0
        sequence of floats of same length as `category_values`, or
        a unique float (recycled); one parameter per category:
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicIndicatorSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=ncategory` variables (probability /
            proportion estimates, of each category);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'estimateIndicator2D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = *dimension, 1
    sx, sy, sz = *spacing, 1.0
    ox, oy, oz = *origin, 0.0

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 2

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # category_values and ncategory (computed)
    try:
        category_values = np.asarray(category_values, dtype='float').reshape(-1)
    except:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is not valid")
        return None

    ncategory = len(category_values)
    if ncategory <= 0:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is empty")
        return None

    # cov_model_for_category
    cov_model_for_category = np.asarray(cov_model_for_category).reshape(-1)
    if not np.all([isinstance(c, gcm.CovModel2D) for c in cov_model_for_category]):
        # cov model will be converted:
        #    as applying modification in an array is persistent at exit,
        #    work on a copy to ensure no modification of the initial entry
        cm_for_cat = copy.deepcopy(cov_model_for_category)
    else:
        cm_for_cat = cov_model_for_category

    cm_for_cat = np.asarray(cm_for_cat).reshape(-1)
    for i in range(len(cm_for_cat)):
        if isinstance(cm_for_cat[i], gcm.CovModel1D):
            cm_for_cat[i] = gcm.covModel1D_to_covModel2D(cm_for_cat[i]) # convert model 1D in 2D
    if len(cm_for_cat) == 1:
        cm_for_cat = np.repeat(cm_for_cat, ncategory)
    elif len(cm_for_cat) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` of invalid length")
        return None
    if not np.all([isinstance(c, gcm.CovModel2D) for c in cm_for_cat]):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` should contains CovModel2D objects")
        return None

    for cov_model in cm_for_cat:
        for el in cov_model.elem:
            # weight
            w = el[1]['w']
            if np.size(w) != 1 and np.size(w) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model: weight ('w') not compatible with simulation grid")
                return None
            # ranges
            if 'r' in el[1].keys():
                for r in el[1]['r']:
                    if np.size(r) != 1 and np.size(r) != nxyz:
                        if verbose > 0:
                            print(f"ERROR ({fname}): covariance model: range ('r') not compatible with simulation grid")
                        return None
            # additional parameter (s)
            if 's' in el[1].keys():
                s  = el[1]['s']
                if np.size(s) != 1 and np.size(s) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): covariance model: parameter ('s') not compatible with simulation grid")
                    return None

        # alpha
        angle = cov_model.alpha
        if np.size(angle) != 1 and np.size(angle) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): covariance model: angle (alpha) not compatible with simulation grid")
            return None

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 1
    elif method == 'ordinary_kriging':
        computationMode = 0
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # data points: x, v
    dataPointSet = []

    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 2) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

        # Aggregate data on grid by taking the most frequent value in grid cell
        xx, yy = x.T
        zz = np.ones_like(xx) * oz + 0.5 * sz
        try:
            xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, v,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op='most_freq')
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): data aggregation ('most_freq') failed")
            return None
        if len(xx_agg) == 0:
            if verbose > 0:
                print(f"ERROR ({fname}): no data point in grid")
            return None

        dataPointSet.append(
            PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
            )

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # Check parameters - use_unique_neighborhood (length)
    use_unique_neighborhood = np.asarray(use_unique_neighborhood, dtype='bool').reshape(-1)
    if len(use_unique_neighborhood) == 1:
        use_unique_neighborhood = np.repeat(use_unique_neighborhood, ncategory)
    elif len(use_unique_neighborhood) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `use_unique_neighborhood` of invalid length")
        return None

    # Check parameters - searchRadiusRelative (length)
    searchRadiusRelative = np.asarray(searchRadiusRelative, dtype='float').reshape(-1)
    if len(searchRadiusRelative) == 1:
        searchRadiusRelative = np.repeat(searchRadiusRelative, ncategory)
    elif len(searchRadiusRelative) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchRadiusRelative` of invalid length")
        return None

    # Check parameters - nneighborMax (length)
    nneighborMax = np.asarray(nneighborMax, dtype='intc').reshape(-1)
    if len(nneighborMax) == 1:
        nneighborMax = np.repeat(nneighborMax, ncategory)
    elif len(nneighborMax) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `nneighborMax` of invalid length")
        return None

    # Check parameters - searchNeighborhoodSortMode (length)
    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode).reshape(-1)
    if len(searchNeighborhoodSortMode) == 1:
        searchNeighborhoodSortMode = np.repeat(searchNeighborhoodSortMode, ncategory)
    elif len(searchNeighborhoodSortMode) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchNeighborhoodSortMode` of invalid length")
        return None

    # If unique neighborhood is used, set searchRadiusRelative to -1
    #    (and initialize nneighborMax, searchNeighborhoodSortMode (unused))
    # else: check the parameters
    for i in range(ncategory):
        if use_unique_neighborhood[i]:
            searchRadiusRelative[i] = -1.0
            nneighborMax[i] = 1
            searchNeighborhoodSortMode[i] = 0

        else:
            if searchRadiusRelative[i] < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
                if verbose > 0:
                    print(f"ERROR ({fname}): a `searchRadiusRelative` is too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
                return None

            if nneighborMax[i] != -1 and nneighborMax[i] <= 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): any `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
                return None

            if searchNeighborhoodSortMode[i] is None:
                # set greatest possible value
                if cm_for_cat[i].is_stationary():
                    searchNeighborhoodSortMode[i] = 2
                else:
                    searchNeighborhoodSortMode[i] = 1
            else:
                if searchNeighborhoodSortMode[i] == 2:
                    if not cm_for_cat[i].is_stationary():
                        if verbose > 0:
                            print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                        return None

            # if searchNeighborhoodSortMode[i] is None:
            #     # set greatest possible value
            #     if cm_for_cat[i].is_stationary():
            #         searchNeighborhoodSortMode[i] = 2
            #     elif cm_for_cat[i].is_orientation_stationary() and cm_for_cat[i].is_range_stationary():
            #         searchNeighborhoodSortMode[i] = 1
            #     else:
            #         searchNeighborhoodSortMode[i] = 0
            # else:
            #     if searchNeighborhoodSortMode[i] == 2:
            #         if not cm_for_cat[i].is_stationary():
            #             if verbose > 0:
            #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
            #             return None
            #     elif searchNeighborhoodSortMode[i] == 1:
            #         if not cm_for_cat[i].is_orientation_stationary() or not cm_for_cat[i].is_range_stationary():
            #             if verbose > 0:
            #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
            #             return None

    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode, dtype='intc')

    # Check parameters - probability
    if probability is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying `probability` not allowed with ordinary kriging")
        #     return None
        probability = np.asarray(probability, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if probability.size not in (ncategory, ncategory*nxyz):
            if verbose > 0:
                print(f"ERROR ({fname}): size of `probability` is not valid")
            return None

    # --- Fill mpds_geosClassicInput structure (C)
    mpds_geosClassicIndicatorInput, flag = fill_mpds_geosClassicIndicatorInput(
        space_dim,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        ncategory,
        category_values,
        outputReportFile,
        computationMode,
        cm_for_cat,
        None,
        dataPointSet,
        mask,
        probability,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        0,
        0)

    if not flag:
        if verbose > 0:
            print(f'ERROR ({fname}): can not fill input structure!')
        return None

    # --- Prepare mpds_geosClassicIOutput structure (C)
    # Allocate mpds_geosClassicOutput
    mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

    # Init mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

    # --- Set progress monitor
    mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
    geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

    # Set function to update progress monitor:
    # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
    # the function
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
    # should be used, but the following function can also be used:
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
    if verbose < 3:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
    else:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if verbose >= 2:
        print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

    # --- Launch "GeosClassicSim" (launch C code)
    # err = geosclassic.MPDSGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
    err = geosclassic.MPDSOMPGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

    # Free memory on C side: mpds_geosClassicIndicatorInput
    geosclassic.MPDSGeosClassicFreeGeosClassicIndicatorInput(mpds_geosClassicIndicatorInput)
    #geosclassic.MPDSFree(mpds_geosClassicIndicatorInput)
    geosclassic.free_MPDS_GEOSCLASSICINDICATORINPUT(mpds_geosClassicIndicatorInput)

    if err:
        if verbose > 0:
            err_message = geosclassic.mpds_get_error_message(-err)
            err_message = err_message.replace('\n', '')
            print(err_message)
        geosclassic_output = None
    else:
        geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

    # Free memory on C side: mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
    #geosclassic.MPDSFree(mpds_geosClassicOutput)
    geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

    # Free memory on C side: mpds_progressMonitor
    #geosclassic.MPDSFree(mpds_progressMonitor)
    geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def estimateIndicator3D(
        category_values,
        cov_model_for_category,
        dimension, spacing=(1.0, 1.0, 1.0), origin=(0.0, 0.0, 0.0),
        method='simple_kriging',
        probability=None,
        x=None, v=None,
        mask=None,
        add_data_point_to_mask=True,
        use_unique_neighborhood=False,
        searchRadiusRelative=1.,
        nneighborMax=12,
        searchNeighborhoodSortMode=None,
        outputReportFile=None,
        nthreads=-1,
        verbose=2):
    """
    Computes estimate probabilities / proportions of categories (indicators) in 2D.
    based on simple or ordinary kriging.

    Interpolation (of the indicator variable of each category) takes place in
    (center of) grid cells, based on simple or ordinary kriging.

    Parameters
    ----------
    category_values : 1D array-like
        sequence of category values; let `ncategory` be the number of categories,
        then:
        - if `ncategory=1`: the unique category value given must not be equal to
        zero; it is used for a binary case with values "unique category value"
        and 0, where 0 indicates the absence of the considered medium; the
        conditioning data values should be equal to"unique category value" or 0
        - if `ncategory>=2`: it is used for a multi-category case with given
        category values (distinct); the conditioning data values should be in the
        `category_values`
    cov_model_for_category : [sequence of] :class:`geone.CovModel.CovModel3D`
        sequence of same length as `category_values` of covariance model in 3D,
        or a unique covariance model in 3D (recycled):
        covariance model for each category
    dimension : 3-tuple of ints
        `dimension=(nx, ny, nz)`, number of cells in the 3D simulation grid along
        each axis
    spacing : 3-tuple of floats, default: (1.0,1.0, 1.0)
        `spacing=(sx, sy, sz)`, cell size along each axis
    origin : 3-tuple of floats, default: (0.0, 0.0, 0.0)
        `origin=(ox, oy, oz)`, origin of the 3D simulation grid (bottom-lower-left
        corner)
    method : str {'simple_kriging', 'ordinary_kriging'}, default: 'simple_kriging'
        type of kriging
    probability : array-like of floats, optional
        probability for each category:
        - sequence of same length as `category_values`:
        probability[i]: probability (proportion, kriging mean value for the
        indicator variable) for category `category_values[i]`, used for
        every grid cell
        - array-like of size ncategory * ngrid_cells, where ncategory is the
        length of `category_values` and ngrid_cells is the number of grid
        cells (the array is reshaped if needed): first ngrid_cells values are
        the probabilities (proportions, kriging mean values for the indicator
        variable) for the first category at grid cells, etc.
        (for non-stationary probailities / proportions);
        by default (`None`): proportion of each category computed from the
        data values (`v`) are used for every grid cell
        note: for ordinary kriging (`method='ordinary_kriging'`), it is used for
        case with no neighbor
    x : 2D array of floats of shape (n, 3), optional
        data points locations, with n the number of data points, each row of `x`
        is the float coordinates of one data point; note: if n=1, a 1D array of
        shape (3,) is accepted
    v : 1D array of floats of shape (n,), optional
        data values at `x` (`v[i]` is the data value at `x[i]`)
    mask : array-like, optional
        mask value at grid cells (value 1 for simulated cells, value 0 for not
        simulated cells); the size of the array must be equal to the number of
        grid cells (the array is reshaped if needed)
    add_data_point_to_mask : bool, default: True
        - if True: any grid cell that contains a data point is added to (the
        simulated part of) the mask (if present), i.e. mask value at those cells
        are set to 1; at the end of the computation the "new mask cells" are
        removed (by setting a missing value (`numpy.nan`) for the variable out of
        the original mask)
        - if False: original mask is kept as given in input, and data point
        falling out of (the simulated part of) the mask (if present) are ignored
    use_unique_neighborhood : bool, default: False
        indicates if a unique neighborhood is used:
        - if True: all data points are taken into account for computing
        estimates and standard deviations; in this case: parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode` are
        not used
        - if False: only data points within a search ellipsoid are taken into
        account for computing estimates and standard deviations (see parameters
        `searchRadiusRelative`, `nneighborMax`, `searchNeighborhoodSortMode`)
    searchRadiusRelative : [sequence of] float(s), default: 1.0
        sequence of floats of same length as `category_values`, or
        a unique float (recycled); one parameter per category:
        indicates how the search ellipsoid is limited (should be positive): let
        r_i be the ranges of the covariance model along its main axes, when
        estimating/simulating a cell x, a cell y is taken into account iff it is
        within the ellipsoid centered at x of half axes equal to
        `searchRadiusRelative`*r_i;
        note: if a range r_i is non-stationary over the grid, its maximal value
        over the grid is considered
    nneighborMax : int, default: 12
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        maximum number of cells retrieved from the search ellipsoid (when
        estimating/simulating a cell), `nneighborMax=-1` for unlimited
    searchNeighborhoodSortMode : int, optional
        sequence of ints of same length as `category_values`, or
        a unique int (recycled); one parameter per category:
        indicates how to sort the search neighboorhood cells (neighbors); they
        are sorted in increasing order according to:
        - `searchNeighborhoodSortMode=0`: distance in the usual axes system
        - `searchNeighborhoodSortMode=1`: distance in the axes sytem supporting
        the covariance model and accounting for anisotropy given by the ranges
        - `searchNeighborhoodSortMode=2`: minus the evaluation of the covariance
        model
        notes:
        - if the covariance model has any non-stationary parameter, then
        `searchNeighborhoodSortMode=2` is not allowed
        - if the covariance model has any non-stationary range or non-stationary
        angle and `searchNeighborhoodSortMode=1`: "maximal ranges" (adapted to
        direction from the central cell) are used to compute distance for sorting
        the neighbors;
        by default (`None`): the greatest possible value is used (i.e. 2 for
        stationary covariance model, or 1 otherwise)
    outputReportFile : str, default: False
        name of the report file (if desired in output); by default (`None`): no
        report file
    nthreads : int, default: -1
        number of thread(s) to use for "GeosClassicIndicatorSim" C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)
    verbose : int, default: 2
        verbose mode, higher implies more printing (info):
        - 0: no display
        - 1: only errors
        - 2: errors and warnings (+ some info)
        - 3 (or >2): all information

    Returns
    -------
    geosclassic_output : dict
        geosclassic output in python, dictionary
            {'image':image, 'nwarning':nwarning, 'warnings':warnings}
        with:
        image : :class:`geone.img.Img`
            output image, with `image.nv=ncategory` variables (probability /
            proportion estimates, of each category);
            note: `image=None` if `mpds_geosClassicOutput->outputImage=NULL`
        nwarning : int
            total number of warning(s) encountered (same warnings can be counted
            several times)
        warnings : list of strs
            list of distinct warnings encountered (can be empty)
    """
    fname = 'estimateIndicator3D'

    # --- Set grid geometry and varname
    # Set grid geometry
    nx, ny, nz = dimension
    sx, sy, sz = spacing
    ox, oy, oz = origin

    nxy = nx * ny
    nxyz = nxy * nz

    # spatial dimension
    space_dim = 3

    # Set varname
    varname = 'V0'

    # --- Check and prepare parameters
    # category_values and ncategory (computed)
    try:
        category_values = np.asarray(category_values, dtype='float').reshape(-1)
    except:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is not valid")
        return None

    ncategory = len(category_values)
    if ncategory <= 0:
        if verbose > 0:
            print(f"ERROR ({fname}): `category_values` is empty")
        return None

    # cov_model_for_category
    cov_model_for_category = np.asarray(cov_model_for_category).reshape(-1)
    if not np.all([isinstance(c, gcm.CovModel3D) for c in cov_model_for_category]):
        # cov model will be converted:
        #    as applying modification in an array is persistent at exit,
        #    work on a copy to ensure no modification of the initial entry
        cm_for_cat = copy.deepcopy(cov_model_for_category)
    else:
        cm_for_cat = cov_model_for_category

    cm_for_cat = np.asarray(cm_for_cat).reshape(-1)
    for i in range(len(cm_for_cat)):
        if isinstance(cm_for_cat[i], gcm.CovModel1D):
            cm_for_cat[i] = gcm.covModel1D_to_covModel3D(cm_for_cat[i]) # convert model 1D in 3D
    if len(cm_for_cat) == 1:
        cm_for_cat = np.repeat(cm_for_cat, ncategory)
    elif len(cm_for_cat) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` of invalid length")
        return None
    if not np.all([isinstance(c, gcm.CovModel3D) for c in cm_for_cat]):
        if verbose > 0:
            print(f"ERROR ({fname}): `cov_model_for_category` should contains CovModel3D objects")
        return None

    for cov_model in cm_for_cat:
        for el in cov_model.elem:
            # weight
            w = el[1]['w']
            if np.size(w) != 1 and np.size(w) != nxyz:
                if verbose > 0:
                    print(f"ERROR ({fname}): covariance model: weight ('w') not compatible with simulation grid")
                return None
            # ranges
            if 'r' in el[1].keys():
                for r in el[1]['r']:
                    if np.size(r) != 1 and np.size(r) != nxyz:
                        if verbose > 0:
                            print(f"ERROR ({fname}): covariance model: range ('r') not compatible with simulation grid")
                        return None
            # additional parameter (s)
            if 's' in el[1].keys():
                s  = el[1]['s']
                if np.size(s) != 1 and np.size(s) != nxyz:
                    if verbose > 0:
                        print(f"ERROR ({fname}): covariance model: parameter ('s') not compatible with simulation grid")
                    return None

        # alpha
        angle = cov_model.alpha
        if np.size(angle) != 1 and np.size(angle) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): covariance model: angle (alpha) not compatible with simulation grid")
            return None

        # beta
        angle = cov_model.beta
        if np.size(angle) != 1 and np.size(angle) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): covariance model: angle (beta) not compatible with simulation grid")
            return None

        # gamma
        angle = cov_model.gamma
        if np.size(angle) != 1 and np.size(angle) != nxyz:
            if verbose > 0:
                print(f"ERROR ({fname}): covariance model: angle (gamma) not compatible with simulation grid")
            return None

    # method
    #    computationMode=0: GEOS_CLASSIC_OK
    #    computationMode=1: GEOS_CLASSIC_SK
    #    computationMode=2: GEOS_CLASSIC_SIM_OK
    #    computationMode=3: GEOS_CLASSIC_SIM_SK
    # if method not in ('simple_kriging', 'ordinary_kriging'):
    #     if verbose > 0:
    #         print(f"ERROR ({fname}): `method` is not valid")
    #     return None
    if method == 'simple_kriging':
        computationMode = 1
    elif method == 'ordinary_kriging':
        computationMode = 0
    else:
        if verbose > 0:
            print(f"ERROR ({fname}): `method` is not valid")
        return None

    # data points: x, v
    dataPointSet = []

    if x is not None:
        x = np.asarray(x, dtype='float').reshape(-1, 3) # cast in 2-dimensional array if needed
        v = np.asarray(v, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if len(v) != x.shape[0]:
            if verbose > 0:
                print(f"(ERROR ({fname}): length of `v` is not valid")
            return None

        # Aggregate data on grid by taking the most frequent value in grid cell
        xx, yy, zz = x.T
        try:
            xx_agg, yy_agg, zz_agg, v_agg = img.aggregateDataPointsWrtGrid(
                                                xx, yy, zz, v,
                                                nx, ny, nz, sx, sy, sz, ox, oy, oz,
                                                op='most_freq')
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): data aggregation ('most_freq') failed")
            return None
        if len(xx_agg) == 0:
            if verbose > 0:
                print(f"ERROR ({fname}): no data point in grid")
            return None

        dataPointSet.append(
            PointSet(npt=v_agg.shape[0], nv=4, val=np.array((xx_agg, yy_agg, zz_agg, v_agg)), varname=['X', 'Y', 'Z', varname])
            )

    # Check parameters - mask
    if mask is not None:
        try:
            mask = np.asarray(mask).reshape(nz, ny, nx)
        except:
            if verbose > 0:
                print(f"ERROR ({fname}): `mask` is not valid")
            return None

    if mask is not None and add_data_point_to_mask:
        # Make a copy of the original mask, to remove value in added mask cell at the end
        mask_original = np.copy(mask)
        # Add cell to mask if needed
        pts = np.zeros((0,3))
        if x is not None:
            pts = np.vstack((pts, np.array((xx_agg, yy_agg, zz_agg)).T))
        if pts.shape[0]:
            im_tmp = img.imageFromPoints(pts,
                        nx=nx, ny=ny, nz=nz,
                        sx=sx, sy=sy, sz=sz,
                        ox=ox, oy=oy, oz=oz,
                        indicator_var=True)
            mask = 1.0*np.any((im_tmp.val[0], mask), axis=0)
            del(im_tmp)
        del(pts)

    # Check parameters - use_unique_neighborhood (length)
    use_unique_neighborhood = np.asarray(use_unique_neighborhood, dtype='bool').reshape(-1)
    if len(use_unique_neighborhood) == 1:
        use_unique_neighborhood = np.repeat(use_unique_neighborhood, ncategory)
    elif len(use_unique_neighborhood) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `use_unique_neighborhood` of invalid length")
        return None

    # Check parameters - searchRadiusRelative (length)
    searchRadiusRelative = np.asarray(searchRadiusRelative, dtype='float').reshape(-1)
    if len(searchRadiusRelative) == 1:
        searchRadiusRelative = np.repeat(searchRadiusRelative, ncategory)
    elif len(searchRadiusRelative) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchRadiusRelative` of invalid length")
        return None

    # Check parameters - nneighborMax (length)
    nneighborMax = np.asarray(nneighborMax, dtype='intc').reshape(-1)
    if len(nneighborMax) == 1:
        nneighborMax = np.repeat(nneighborMax, ncategory)
    elif len(nneighborMax) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `nneighborMax` of invalid length")
        return None

    # Check parameters - searchNeighborhoodSortMode (length)
    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode).reshape(-1)
    if len(searchNeighborhoodSortMode) == 1:
        searchNeighborhoodSortMode = np.repeat(searchNeighborhoodSortMode, ncategory)
    elif len(searchNeighborhoodSortMode) != ncategory:
        if verbose > 0:
            print(f"ERROR ({fname}): `searchNeighborhoodSortMode` of invalid length")
        return None

    # If unique neighborhood is used, set searchRadiusRelative to -1
    #    (and initialize nneighborMax, searchNeighborhoodSortMode (unused))
    # else: check the parameters
    for i in range(ncategory):
        if use_unique_neighborhood[i]:
            searchRadiusRelative[i] = -1.0
            nneighborMax[i] = 1
            searchNeighborhoodSortMode[i] = 0

        else:
            if searchRadiusRelative[i] < geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN:
                if verbose > 0:
                    print(f"ERROR ({fname}): a `searchRadiusRelative` is too small (should be at least {geosclassic.MPDS_GEOSCLASSIC_SEARCHRADIUSRELATIVE_MIN})")
                return None

            if nneighborMax[i] != -1 and nneighborMax[i] <= 0:
                if verbose > 0:
                    print(f"ERROR ({fname}): any `nneighborMax` should be greater than 0 or equal to -1 (unlimited)")
                return None

            if searchNeighborhoodSortMode[i] is None:
                # set greatest possible value
                if cm_for_cat[i].is_stationary():
                    searchNeighborhoodSortMode[i] = 2
                else:
                    searchNeighborhoodSortMode[i] = 1
            else:
                if searchNeighborhoodSortMode[i] == 2:
                    if not cm_for_cat[i].is_stationary():
                        if verbose > 0:
                            print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
                        return None

            # if searchNeighborhoodSortMode[i] is None:
            #     # set greatest possible value
            #     if cm_for_cat[i].is_stationary():
            #         searchNeighborhoodSortMode[i] = 2
            #     elif cm_for_cat[i].is_orientation_stationary() and cm_for_cat[i].is_range_stationary():
            #         searchNeighborhoodSortMode[i] = 1
            #     else:
            #         searchNeighborhoodSortMode[i] = 0
            # else:
            #     if searchNeighborhoodSortMode[i] == 2:
            #         if not cm_for_cat[i].is_stationary():
            #             if verbose > 0:
            #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=2` not allowed with non-stationary covariance model")
            #             return None
            #     elif searchNeighborhoodSortMode[i] == 1:
            #         if not cm_for_cat[i].is_orientation_stationary() or not cm_for_cat[i].is_range_stationary():
            #             if verbose > 0:
            #                 print(f"ERROR ({fname}): `searchNeighborhoodSortMode=1` not allowed with non-stationary range or non-stationary orientation in covariance model")
            #             return None

    searchNeighborhoodSortMode = np.asarray(searchNeighborhoodSortMode, dtype='intc')

    # Check parameters - probability
    if probability is not None:
        # if method == 'ordinary_kriging':
        #     if verbose > 0:
        #         print(f"ERROR ({fname}): specifying `probability` not allowed with ordinary kriging")
        #     return None
        probability = np.asarray(probability, dtype='float').reshape(-1) # cast in 1-dimensional array if needed
        if probability.size not in (ncategory, ncategory*nxyz):
            if verbose > 0:
                print(f"ERROR ({fname}): size of `probability` is not valid")
            return None

    # --- Fill mpds_geosClassicInput structure (C)
    mpds_geosClassicIndicatorInput, flag = fill_mpds_geosClassicIndicatorInput(
        space_dim,
        nx, ny, nz,
        sx, sy, sz,
        ox, oy, oz,
        varname,
        ncategory,
        category_values,
        outputReportFile,
        computationMode,
        cm_for_cat,
        None,
        dataPointSet,
        mask,
        probability,
        searchRadiusRelative,
        nneighborMax,
        searchNeighborhoodSortMode,
        0,
        0)

    if not flag:
        if verbose > 0:
            print(f'ERROR ({fname}): can not fill input structure!')
        return None

    # --- Prepare mpds_geosClassicIOutput structure (C)
    # Allocate mpds_geosClassicOutput
    mpds_geosClassicOutput = geosclassic.malloc_MPDS_GEOSCLASSICOUTPUT()

    # Init mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicInitGeosClassicOutput(mpds_geosClassicOutput)

    # --- Set progress monitor
    mpds_progressMonitor = geosclassic.malloc_MPDS_PROGRESSMONITOR()
    geosclassic.MPDSInitProgressMonitor(mpds_progressMonitor)

    # Set function to update progress monitor:
    # according to geosclassic.MPDS_SHOW_PROGRESS_MONITOR set to 4 for compilation of py module
    # the function
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr
    # should be used, but the following function can also be used:
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr: no output
    #    mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor1_ptr: warning only
    if verbose < 3:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor0_ptr
    else:
        mpds_updateProgressMonitor = geosclassic.MPDSUpdateProgressMonitor4_ptr

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    if verbose >= 2:
        print('Geos-Classic running... [VERSION {:s} / BUILD NUMBER {:s} / OpenMP {:d} thread(s)]'.format(geosclassic.MPDS_GEOS_CLASSIC_VERSION_NUMBER, geosclassic.MPDS_GEOS_CLASSIC_BUILD_NUMBER, nth))
        sys.stdout.flush()
        sys.stdout.flush() # twice!, so that the previous print is flushed before launching GeosClassic...

    # --- Launch "GeosClassicSim" (launch C code)
    # err = geosclassic.MPDSGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor )
    err = geosclassic.MPDSOMPGeosClassicIndicatorSim(mpds_geosClassicIndicatorInput, mpds_geosClassicOutput, mpds_progressMonitor, mpds_updateProgressMonitor, nth)

    # Free memory on C side: mpds_geosClassicIndicatorInput
    geosclassic.MPDSGeosClassicFreeGeosClassicIndicatorInput(mpds_geosClassicIndicatorInput)
    #geosclassic.MPDSFree(mpds_geosClassicIndicatorInput)
    geosclassic.free_MPDS_GEOSCLASSICINDICATORINPUT(mpds_geosClassicIndicatorInput)

    if err:
        if verbose > 0:
            err_message = geosclassic.mpds_get_error_message(-err)
            err_message = err_message.replace('\n', '')
            print(err_message)
        geosclassic_output = None
    else:
        geosclassic_output = geosclassic_output_C2py(mpds_geosClassicOutput, mpds_progressMonitor)

    # Free memory on C side: mpds_geosClassicOutput
    geosclassic.MPDSGeosClassicFreeGeosClassicOutput(mpds_geosClassicOutput)
    #geosclassic.MPDSFree(mpds_geosClassicOutput)
    geosclassic.free_MPDS_GEOSCLASSICOUTPUT(mpds_geosClassicOutput)

    # Free memory on C side: mpds_progressMonitor
    #geosclassic.MPDSFree(mpds_progressMonitor)
    geosclassic.free_MPDS_PROGRESSMONITOR(mpds_progressMonitor)

    if geosclassic_output is not None and mask is not None and add_data_point_to_mask:
        # Remove the value out of the original mask (using its copy see above)
        geosclassic_output['image'].val[:, mask_original==0.0] = np.nan

    if verbose >= 2 and geosclassic_output:
        print('Geos-Classic run complete')

    # Show (print) encountered warnings
    if verbose >= 2 and geosclassic_output and geosclassic_output['nwarning']:
        print('\nWarnings encountered ({} times in all):'.format(geosclassic_output['nwarning']))
        for i, warning_message in enumerate(geosclassic_output['warnings']):
            print('#{:3d}: {}'.format(i+1, warning_message))

    return geosclassic_output
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def imgDistanceImage(
        input_image,
        distance_type='L2',
        distance_negative=False,
        nthreads=-1):
    """
    Computes distance to a given subset in an image.

    This function computes the image of the distances to the set of non zero
    values in the input image. The distances are computed for each variable v
    over the image grid: distance to the set S = {v!=0}. Distance is equal to
    zero for all cells in S if the keyword argument `distance_negative=False`
    (default). If `distance_negative=True`, the distance to the border of S is
    computed for the cells in the interior of S (i.e. in S but not on the
    border), and the opposite (negative) value is retrieved for that cells.
    The output image has the same number of variable(s) and the same size
    (grid geometry) as the input image.

    Parameters
    ----------
    input_image : :class:`geone.img.Img`
        input image
    distance_type : str {'L1', 'L2'}, default: 'L2'
        type of distance
    distance_negative : bool, default: True
        - if True: negative distance are retrieved for the grid cells in S={v!=0}
        (where v denotes the value of a variable in the input image) (distance
        set to zero on the border of S), see above
        - if False: distance is set to zero for all grid cells in S={v!=0}
        (where v denotes the value of a variable in the input image), see above
    nthreads : int, default: -1
        number of thread(s) to use for C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)

    Returns
    -------
    output_image : :class:`geone.img.Img`
        image with same grid as the input image and same number of variable,
        distance to the set S={v!=0} (where v denotes the value of a variable
        in the input image), for each variable

    Notes
    ------
    Algorithm from "A GENERAL ALGORITHM FOR COMPUTING DISTANCE TRANSFORMS IN
    LINEAR TIME" by A. MEIJSTER, J.B.T.M. ROERDINK, and W.H. HESSELINK
    """
    fname = 'imgDistanceImage'

    # --- Check
    if distance_type not in ('L1', 'L2'):
        print(f"ERROR ({fname}): unknown `distance_type`")
        return None

    # Set input image "in C"
    input_image_c = img_py2C(input_image)

    # Allocate output image "in C"
    output_image_c = geosclassic.malloc_MPDS_IMAGE()
    geosclassic.MPDSInitImage(output_image_c)

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    # --- Compute distances (launch C code)
    if distance_type == 'L1':
        if distance_negative:
            err = geosclassic.MPDSOMPImageDistanceL1Sign(input_image_c, output_image_c, nth)
        else:
            err = geosclassic.MPDSOMPImageDistanceL1(input_image_c, output_image_c, nth)
    elif distance_type == 'L2':
        if distance_negative:
            err = geosclassic.MPDSOMPImageDistanceEuclideanSign(input_image_c, output_image_c, nth)
        else:
            err = geosclassic.MPDSOMPImageDistanceEuclidean(input_image_c, output_image_c, nth)
    else:
        print(f"ERROR ({fname}): `distance_type` not valid")
        return None

    # --- Retrieve output image "in python"
    if err:
        err_message = geosclassic.mpds_get_error_message(-err)
        err_message = err_message.replace('\n', '')
        print(err_message)
        output_image = None
    else:
        output_image = img_C2py(output_image_c)

    # Free memory on C side: input_image_c
    geosclassic.MPDSFreeImage(input_image_c)
    #geosclassic.MPDSFree(input_image_c)
    geosclassic.free_MPDS_IMAGE(input_image_c)

    # Free memory on C side: output_image_c
    geosclassic.MPDSFreeImage(output_image_c)
    #geosclassic.MPDSFree(output_image_c)
    geosclassic.free_MPDS_IMAGE(output_image_c)

    return output_image
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def imgGeobodyImage(
        input_image,
        var_index=0,
        bound_inf=0.0,
        bound_sup=None,
        bound_inf_excluded=True,
        bound_sup_excluded=True,
        complementary_set=False,
        connect_type='connect_face'):
    """
    Computes the geobody image (map) for one variable of the input image.

    For the considered variable v and any location x in the input image, an
    indicator I is defined as
        I(x) = 1 if v(x) is between `bound_inf` and `bound_sup`
        I(x) = 0 otherwise
    Then lower (resp. upper) bound `bound_inf` (resp. `bound_sup`) is exluded
    from the set I=1 if `bound_inf_excluded=True` (resp.
    `bound_sup_excluded=True`) is True or included if `bound_inf_excluded=False`
    (resp. `bound_sup_excluded=False`); hence:
    - if `bound_inf_excluded, bound_sup_excluded = (True, True)`:
    I(x) = 1 iff `bound_inf` < v(x) < `bound_sup`
    (default: I(x) = 1 iff 0 < v(x))
    - if `bound_inf_excluded, bound_sup_excluded = (True, False)`:
    I(x) = 1 iff `bound_inf` < v(x) <= `bound_sup`
    - if `bound_inf_excluded, bound_sup_excluded = (False, True)`:
    I(x) = 1 iff `bound_inf` <= v(x) < `bound_sup`
    - if `bound_inf_excluded, bound_sup_excluded = (False, False)`:
    I(x) = 1 iff `bound_inf` <= v(x) <= `bound_sup`

    If `complementary_set=True`, the variable IC(x) = 1 - I(x) is used
    instead of variable I, i.e. the set I=0 and I=1 are swapped.

    The geobody image (map) is computed for the indicator variable I, which
    consists in labelling the connected components from 1 to n, i.e.
        C(x) = 0     if I(x) = 0
        C(x) = k > 0 if I(x) = 1 and x is in the k-th connected component

    Two cells x and y in the grid are said connected, x <-> y, if there exists
    a path between x and y going composed of adjacent cells, within the set I=1.
    Following this definition, we have
        x <-> y iff C(x) = C(y) > 0

    The definition of adjacent cells is set according to the parameter
    `connect_type`:
    - `connect_type='connect_face'` (default):
    two grid cells are adjacent if they have a common face
    - `connect_type='connect_face_edge'`:
    two grid cells are adjacent if they have a common face or a common edge
    - `connect_type='connect_face_edge_corner'`:
    two grid cells are adjacent if they have a common face or a common edge
    or a common corner

    Parameters
    ----------
    input_image : :class:`geone.img.Img`
        input image
    var_index : int, default: 0
        index of the considered variable in input image
    bound_inf : float, default: 0.0
        lower bound of the interval defining the indicator variable
    bound_sup : float, optional
        upper bound of the interval defining the indicator variable;
        by default (`None`): `bound_sup=numpy.inf` is used (no upper bound)
    bound_inf_excluded : bool, default: True
        lower bound is excluded from the interval defining the indicator
        variable (True) or included (False)
    bound_sup_excluded : bool, default: True
        upper bound is excluded from the interval defining the indicator
        variable (True) or included (False)
    complementary_set : bool, default: False
        - if True: the complementary indicator variable (IC = 1-I, see above) is
        used
        - if False: the indicator variable I (see above) is used
    connect_type : str {'connect_face', 'connect_face_edge',
            'connect_face_edge_corner'}, default: 'connect_face'
        indicates which definition of adjacent cells is used (see above)

    Returns
    -------
    output_image : :class:`geone.img.Img`
        image with same grid as the input image and one variable, the geobody
        label (see above)

    Notes
    -----
    Algorithm used is described in: Hoshen and Kopelman (1976) Physical Review B,
    14(8):3438.
    """
    fname = 'imgGeobodyImage'

    # --- Check
    if connect_type not in ('connect_face', 'connect_face_edge', 'connect_face_edge_corner'):
        print(f"ERROR ({fname}): unknown `connect_type`")
        return None

    if var_index < 0 or var_index >= input_image.nv:
        print(f"ERROR ({fname}): `var_index` not valid")
        return None

    if bound_sup is None:
        bound_sup = 1. + np.nanmax(input_image.val[var_index])

    # Allocate variable in C
    rangeValueMin_c = geosclassic.new_real_array(1)
    geosclassic.mpds_set_real_vector_from_array(rangeValueMin_c, 0, np.array([bound_inf], dtype='float'))

    rangeValueMax_c = geosclassic.new_real_array(1)
    geosclassic.mpds_set_real_vector_from_array(rangeValueMax_c, 0, np.array([bound_sup], dtype='float'))

    ngeobody_c = geosclassic.new_int_array(1)

    # Set input image "in C"
    input_image_c = img_py2C(input_image)

    # Allocate output image "in C"
    output_image_c = geosclassic.malloc_MPDS_IMAGE()
    geosclassic.MPDSInitImage(output_image_c)

    # --- Compute geobody image (launch C code)
    if connect_type == 'connect_face':
        g = geosclassic.MPDSImageGeobody6
    elif connect_type == 'connect_face_edge':
        g = geosclassic.MPDSImageGeobody18
    elif connect_type == 'connect_face_edge_corner':
        g = geosclassic.MPDSImageGeobody26
    else:
        print(f"ERROR ({fname}): `connect_type` not valid")
        return None

    err = g(input_image_c, output_image_c, var_index,
            complementary_set,
            1, rangeValueMin_c, rangeValueMax_c, bound_inf_excluded, bound_sup_excluded,
            ngeobody_c)

    # --- Retrieve output image "in python"
    if err:
        err_message = geosclassic.mpds_get_error_message(-err)
        err_message = err_message.replace('\n', '')
        print(err_message)
        output_image = None
    else:
        output_image = img_C2py(output_image_c)
        # # Retrieve the number of geobody (not used, this is simple the max of the output image (max label))
        # ngeobody = np.zeros(1, dtype='intc') # 'intc' for C-compatibility
        # geosclassic.mpds_get_array_from_int_vector(ngeobody_c, 0, ngeobody)
        # ngeobody = ngeobody[0]

    # Free memory on C side: input_image_c
    geosclassic.MPDSFreeImage(input_image_c)
    #geosclassic.MPDSFree(input_image_c)
    geosclassic.free_MPDS_IMAGE(input_image_c)

    # Free memory on C side: output_image_c
    geosclassic.MPDSFreeImage(output_image_c)
    #geosclassic.MPDSFree(output_image_c)
    geosclassic.free_MPDS_IMAGE(output_image_c)

    # Free memory on C side: rangeValueMin_c, rangeValueMax_c, ngeobody_c
    geosclassic.delete_real_array(rangeValueMin_c)
    geosclassic.delete_real_array(rangeValueMax_c)
    geosclassic.delete_int_array(ngeobody_c)
    # geosclassic.MPDSFree(rangeValueMin_c)
    # geosclassic.MPDSFree(rangeValueMax_c)
    # geosclassic.MPDSFree(ngeobody_c)

    return output_image
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def imgTwoPointStatisticsImage(
        input_image,
        var_index=0,
        hx_min=None,
        hx_max=None,
        hx_step=1,
        hy_min=None,
        hy_max=None,
        hy_step=1,
        hz_min=None,
        hz_max=None,
        hz_step=1,
        stat_type='covariance',
        show_progress=False,
        nthreads=-1):
    """
    Computes two-point statistics image (map) for one variable of the input image.

    Two-point statistics g(h) as function of lag vector h are computed. Let v(x)
    the value of the considered variable at grid cell x; the available two-point
    statistics (according to parameter `stat_type`) are:
        correlogram            : g(h) = cor(v(x), v(x+h)) (linear correlation)
        connectivity_func0     : g(h) = P(v(x)=v(x+h) > 0)
        connectivity_func1     : g(h) = P(v(x)=v(x+h) > 0 | v(x) > 0)
        connectivity_func2     : g(h) = P(v(x)=v(x+h) > 0 | v(x) > 0, v(x+h) > 0)
        covariance (default)   : g(h) = cov(v(x), v(x+h))
        covariance_not_centered: g(h) = E[v(x)*v(x+h)]
        transiogram            : g(h) = P(v(x+h) > 0 | v(x) > 0)
        variogram              : g(h) = 0.5 * E[(v(x)-v(x+h))**2]

    Notes:
    - a transiogram can be applied on a binary variable
    - a connectivity function (connectivity_func[012]) should be applied on
        a variable consisting of geobody (connected component) labels,
        i.e. input_image should be the output image returned by the function
        `imgGeobodyImage`;
        in that case, denoting I(x) is the indicator variable defined as
        I(x) = 1 iff v(x)>0, the variable v is the geobody label for the
        indicator variable I an we have the relations
            P(v(x) = v(x+h) > 0)
            = P(v(x)=v(x+h) > 0 | v(x) > 0, v(x+h) > 0) * P(v(x) > 0, v(x+h) > 0)
            = P(v(x)=v(x+h) > 0 | v(x) > 0, v(x+h) > 0) * P(I(x)*I(x+h))
            = P(v(x)=v(x+h) > 0 | v(x) > 0, v(x+h) > 0) * E(I(x)*I(x+h))
        i.e.
            P(x <-> x+h) = P(x <-> x+h | x, x+h in {I=1}) * E(I(x)*I(x+h))
        "connectivity_func0(v) = connectivity_func2(v)*covariance_not_centered(I)"
        (see definition of "is connected to" (<->) in the function
        `imgGeobodyImage`).
        See reference:
        - Renard P, Allard D (2013), Connectivity metrics for subsurface flow
        and transport. Adv Water Resour 51:168–196.
        https://doi.org/10.1016/j.advwatres.2011.12.001

    The output image has one variable and its grid is defined according the
    considered lags h defined according to the parameters:
        `hx_min`, `hx_max`, `hx_step`,
        `hy_min`, `hy_max`, `hy_step`,
        `hz_min`, `hz_max`, `hz_step`.

    The minimal (resp. maximal) lag in x direction, expressed in number of cells
    (in the input image), is given by `hx_min` (resp. `hx_max`); every `hx_step`
    cells from `hx_min` up to at most `hx_max` are considered as lag in x
    direction. Hence, the output image grid will have
    `1 + (hx_max-hx_min)//hx_step` cells in x direction.
    This is similar for y and z direction.

    For example, `hx_min=-10, hx_max=10, hx_step=2` implies lags in x direction
    of -10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10 cells (in input image).

    Parameters
    ----------
    input_image : :class:`geone.img.Img`
        input image
    var_index : int, default: 0
        index of the considered variable in input image
    hx_min : int, optional
        min lag along x axis, expressed in number of cells;
        by default (`None`): `hx_min = - (input_image.nx // 2)` is used
    hx_max : int, optional
        max lag along x axis, expressed in number of cells;
        by default (`None`): `hx_max = input_image.nx // 2` is used
    hx_step : int, optional
        step for lags along x axis, expressed in number of cells;
        by default (`None`): `hx_step = 1` is used
    hy_min : int, optional
        min lag along y axis, expressed in number of cells;
        by default (`None`): `hy_min = - (input_image.ny // 2)` is used
    hy_max : int, optional
        max lag along y axis, expressed in number of cells;
        by default (`None`): `hy_max = input_image.ny // 2` is used
    hy_step : int, optional
        step for lags along y axis, expressed in number of cells;
        by default (`None`): `hy_step = 1` is used
    hz_min : int, optional
        min lag along z axis, expressed in number of cells;
        by default (`None`): `hz_min = - (input_image.nz // 2)` is used
    hz_max : int, optional
        max lag along z axis, expressed in number of cells;
        by default (`None`): `hz_max = input_image.nz // 2` is used
    hz_step : int, optional
        step for lags along z axis, expressed in number of cells;
        by default (`None`): `hz_step = 1` is used
    stat_type : str {'correlogram',
                'connectivity_func0', 'connectivity_func1', 'connectivity_func2',
                'covariance', 'covariance_not_centered',
                'transiogram', 'variogram'}, default: 'covariance'
        type of two-point statistics  (see above);
        for type 'connectivity_func[012]', the input image is assumed to be a
        geobody image (see above)
    show_progress : bool, default: False
        indicates if progress is displayed (True) or not (False)
    nthreads : int, default: -1
        number of thread(s) to use for C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)

    Returns
    -------
    output_image : :class:`geone.img.Img`
        two-point statistics image (one variable)
    """
    fname = 'imgTwoPointStatisticsImage'

    # --- Check
    if stat_type not in ('correlogram',
                         'connectivity_func0',
                         'connectivity_func1',
                         'connectivity_func2',
                         'covariance',
                         'covariance_not_centered',
                         'transiogram',
                         'variogram'):
        print(f"ERROR ({fname}): unknown `stat_type`")
        return None

    if var_index < 0 or var_index >= input_image.nv:
        print(f"ERROR ({fname}): `var_index` not valid")
        return None

    # --- Prepare parameters
    if hx_min is None:
        hx_min = -(input_image.nx // 2)
    else:
        hx_min = int(hx_min) # ensure int type

    if hx_max is None:
        hx_max = input_image.nx // 2
    else:
        hx_max = int(hx_max) # ensure int type

    hx_step = int(hx_step) # ensure int type

    if hy_min is None:
        hy_min = -(input_image.ny // 2)
    else:
        hy_min = int(hy_min) # ensure int type

    if hy_max is None:
        hy_max = input_image.ny // 2
    else:
        hy_max = int(hy_max) # ensure int type

    hy_step = int(hy_step) # ensure int type

    if hz_min is None:
        hz_min = -(input_image.nz // 2)
    else:
        hz_min = int(hz_min) # ensure int type

    if hz_max is None:
        hz_max = input_image.nz // 2
    else:
        hz_max = int(hz_max) # ensure int type

    hz_step = int(hz_step) # ensure int type

    # Set input image "in C"
    input_image_c = img_py2C(input_image)

    # Allocate output image "in C"
    output_image_c = geosclassic.malloc_MPDS_IMAGE()
    geosclassic.MPDSInitImage(output_image_c)

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    # --- Compute two-point statistics (launch C code)
    if stat_type == 'correlogram':
        g = geosclassic.MPDSOMPImageCorrelogram
    elif stat_type == 'covariance':
        g = geosclassic.MPDSOMPImageCovariance
    elif stat_type == 'connectivity_func0':
        g = geosclassic.MPDSOMPImageConnectivityFunction0
    elif stat_type == 'connectivity_func1':
        g = geosclassic.MPDSOMPImageConnectivityFunction1
    elif stat_type == 'connectivity_func2':
        g = geosclassic.MPDSOMPImageConnectivityFunction2
    elif stat_type == 'covariance_not_centered':
        g = geosclassic.MPDSOMPImageCovarianceNotCentred
    elif stat_type == 'transiogram':
        g = geosclassic.MPDSOMPImageTransiogram
    elif stat_type == 'variogram':
        g = geosclassic.MPDSOMPImageVariogram
    else:
        print(f"ERROR ({fname}): `stat_type` not valid")
        return None

    err = g(input_image_c, output_image_c, var_index,
            hx_min, hx_max, hx_step,
            hy_min, hy_max, hy_step,
            hz_min, hz_max, hz_step,
            show_progress, nth)

    # --- Retrieve output image "in python"
    if err:
        err_message = geosclassic.mpds_get_error_message(-err)
        err_message = err_message.replace('\n', '')
        print(err_message)
        output_image = None
    else:
        output_image = img_C2py(output_image_c)

    # Free memory on C side: input_image_c
    geosclassic.MPDSFreeImage(input_image_c)
    #geosclassic.MPDSFree(input_image_c)
    geosclassic.free_MPDS_IMAGE(input_image_c)

    # Free memory on C side: output_image_c
    geosclassic.MPDSFreeImage(output_image_c)
    #geosclassic.MPDSFree(output_image_c)
    geosclassic.free_MPDS_IMAGE(output_image_c)

    return output_image
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def imgConnectivityGammaValue(
        input_image,
        var_index=0,
        geobody_image_in_input=False,
        complementary_set=False,
        connect_type='connect_face'):
    """
    Computes the Gamma value for one variable v of the input image.

    The Gamma value is defined as
        Gamma = 1/m^2 * sum_{i=1,...,N} n(i)^2,
    where
        N is the number of connected components (geobodies)
            of the set {v>0}
        n(i) is the size (number of cells) in the i-th connected component
        m is the size (number of cells) of the set {v>0},
        note: Gamma is set to 1.0 if N = 0
    i.e. the indicator variable I(x) = 1 iff v(x) > 0, is considered.

    The definition of adjacent cells, required to compute the connected
    components, is set according to the parameter `connect_type`:
    - `connect_type='connect_face'` (default):
    two grid cells are adjacent if they have a common face
    - `connect_type='connect_face_edge'`:
    two grid cells are adjacent if they have a common face or a common edge
    - `connect_type='connect_face_edge_corner'`:
    two grid cells are adjacent if they have a common face or a common edge
    or a common corner

    Parameters
    ----------
    input_image : :class:`geone.img.Img`
        input image
    var_index : int, default: 0
        index of the considered variable in input image
    geobody_image_in_input : bool, default: False
        - if True: the input image is already a geobody image (variable
        `var_index` is the geobody label); in this case the parameters
        `complementary_set` and `connect_type` are not used
        - False: the geobody image for the indicator variable {v>0} (with v
        the variable of index `var_index`) is computed
    complementary_set : bool, default: False
        - if True: the complementary indicator variable (IC = 1-I, see above) is
        used
        - if False: the indicator variable I (see above) is used
    connect_type : str {'connect_face', 'connect_face_edge',
            'connect_face_edge_corner'}, default: 'connect_face'
        indicates which definition of adjacent cells is used (see above)

    Returns
    -------
    gamma : float
        Gamma value (see above)

    Notes
    -----
    The Gamma value is a global indicator of the connectivity for the binary
    image of variable I
    See reference:
    - Renard P, Allard D (2013), Connectivity metrics for subsurface flow and
    transport. Adv Water Resour 51:168–196.
    https://doi.org/10.1016/j.advwatres.2011.12.001
    """
    fname = 'imgConnectivityGammaValue'

    # --- Check and prepare
    if var_index < 0 or var_index >= input_image.nv:
        print(f"ERROR ({fname}): `var_index` not valid")
        return None

    if not geobody_image_in_input and connect_type not in ('connect_face', 'connect_face_edge', 'connect_face_edge_corner'):
        print(f"ERROR ({fname}): unknown `connect_type`")
        return None

    # Compute geobody image
    if not geobody_image_in_input:
        im_geobody = imgGeobodyImage(input_image,
                                     var_index,
                                     bound_inf=0.0,
                                     bound_sup=None,
                                     bound_inf_excluded=True,
                                     bound_sup_excluded=True,
                                     complementary_set=complementary_set,
                                     connect_type=connect_type)
        iv = 0
    else:
        im_geobody = input_image
        iv = var_index

    # Compute Gamma value
    if im_geobody is not None:
        ngeo = int(im_geobody.val[iv].max())
        if ngeo == 0:
            gamma = 1.0
        else:
            gamma = np.sum(np.array([float(np.sum(im_geobody.val[iv] == i))**2 for i in np.arange(1, ngeo+1)])) / float(np.sum(im_geobody.val[iv] != 0))**2
    else:
        return None

    return gamma
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def imgConnectivityGammaCurves(
        input_image,
        threshold_min=None,
        threshold_max=None,
        nthreshold=50,
        connect_type='connect_face',
        show_progress=False,
        nthreads=-1):
    """
    Computes Gamma curves for an input image with one continuous variable.

    For a threshold t:
    - we consider the indicator variable I(t) defined as
    I(t)(x) = 1 iif v(x) <= t
    - we compute
    gamma(t) = 1/m^2 * sum_{i=1,...,N} n(i)^2,
    where
        - N is the number of connected components (geobodies) of the set {I(t)=1}
        - n(i) is the size (number of cells) in the i-th connected component
        - m is the size (number of cells) of the set {I(t)=1}
    note: gamma(t) is set to 1.0 if N = 0
    - we compute also gammaC(t), the gamma value for the complementary set
    {IC(t)=1} where IC(t)(x) = 1 - I(t)(x).
    This is repeated for different threshold values t, which gives the curves
    gamma(t) and gammaC(t).

    The definition of adjacent cells, required to compute the connected
    components, is set according to the parameter `connect_type`:
    - `connect_type='connect_face'` (default):
    two grid cells are adjacent if they have a common face
    - `connect_type='connect_face_edge'`:
    two grid cells are adjacent if they have a common face or a common edge
    - `connect_type='connect_face_edge_corner'`:
    two grid cells are adjacent if they have a common face or a common edge
    or a common corner

    Parameters
    ----------
    input_image : :class:`geone.img.Img`
        input image, it should have only one variable
    threshold_min : float, optional
        minimal value of the threshold;
        by default (`None`): min of the input variable values minus 1.e-10
    threshold_max : float, optional
        maximal value of the threshold;
        by default (`None`): max of the input variable values plus 1.e-10
    nthreshod : int, default: 50
        number of thresholds considered, the threshold values are
        `numpy.linspace(threshold_min, threshold_max, nthreshold)`
    connect_type : str {'connect_face', 'connect_face_edge',
            'connect_face_edge_corner'}, default: 'connect_face'
        indicates which definition of adjacent cells is used (see above)
    show_progress : bool, default: False
        indicates if progress is displayed (True) or not (False)
    nthreads : int, default: -1
        number of thread(s) to use for C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)

    Returns
    -------
    out_array : 2D array of floats of shape (ntrheshold, 3)
        the columns correspond to: the threshold values, the gamma values, and
        the gammaC values, i.e.:
        - `out_array[i, 0]`:
        `numpy.linspace(threshold_min, threshold_max, nthreshold)`
        - `out_array[i, 1]`: gamma(out_array[i, 0])
        - `out_array[i, 2]`: gammaC(out_array[i, 0])

    Notes
    -----
    The Gamma value gamma(t) (resp. gammaC(t)) is a global indicator of the
    connectivity for the binary variable I(t) (resp. IC(t)).
    See reference:
    - Renard P, Allard D (2013), Connectivity metrics for subsurface flow and
    transport. Adv Water Resour 51:168–196.
    https://doi.org/10.1016/j.advwatres.2011.12.001
    """
    fname = 'imgConnectivityGammaCurves'

    # --- Check and prepare
    if input_image.nv != 1:
        print(f'ERROR ({fname}): input image must have one variable only')
        return None

    if threshold_min is None:
        threshold_min = np.nanmin(input_image.val) - 1.e-10

    if threshold_max is None:
        threshold_max = np.nanmax(input_image.val) + 1.e-10

    if threshold_min > threshold_max:
        print(f"ERROR ({fname}): `threshold_min` is greater than `threshold_max`")
        return None

    if nthreshold < 0:
        print(f"ERROR ({fname}): `nthreshold` is negative")
        return None
    elif nthreshold == 1:
        threshold_step = 1.0
    else:
        threshold_step = (threshold_max - threshold_min) / (nthreshold - 1)

    if threshold_step < geosclassic.MPDS_EPSILON:
        print(f'ERROR ({fname}): threshold step too small')
        return None

    if connect_type not in ('connect_face', 'connect_face_edge', 'connect_face_edge_corner'):
        print(f"ERROR ({fname}): unknown `connect_type`")
        return None

    # Set input image "in C"
    input_image_c = img_py2C(input_image)

    # Allocate output variable in C
    threshold_c = geosclassic.new_real_array(nthreshold)
    gamma_c = geosclassic.new_real_array(nthreshold)
    gammaC_c = geosclassic.new_real_array(nthreshold)

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    # --- Compute Gamma curves (launch C code)
    if connect_type == 'connect_face':
        g = geosclassic.MPDSOMPImageConnectivity6GlobalIndicatorCurve
    elif connect_type == 'connect_face_edge':
        g = geosclassic.MPDSOMPImageConnectivity18GlobalIndicatorCurve
    elif connect_type == 'connect_face_edge_corner':
        g = geosclassic.MPDSOMPImageConnectivity26GlobalIndicatorCurve
    else:
        print(f"ERROR ({fname}): `connect_type` not valid")
        return None

    err = g(input_image_c, nthreshold, threshold_min, threshold_step,
            threshold_c, gamma_c, gammaC_c,
            show_progress, nth)

    # --- Retrieve output "in python"
    if err:
        err_message = geosclassic.mpds_get_error_message(-err)
        err_message = err_message.replace('\n', '')
        print(err_message)
        out_array = None
    else:
        threshold = np.zeros(nthreshold)
        geosclassic.mpds_get_array_from_real_vector(threshold_c, 0, threshold)

        gamma = np.zeros(nthreshold)
        geosclassic.mpds_get_array_from_real_vector(gamma_c, 0, gamma)

        gammaC = np.zeros(nthreshold)
        geosclassic.mpds_get_array_from_real_vector(gammaC_c, 0, gammaC)

        out_array = np.array((threshold, gamma, gammaC)).reshape(3, -1).T

    # Free memory on C side: input_image_c
    geosclassic.MPDSFreeImage(input_image_c)
    #geosclassic.MPDSFree(input_image_c)
    geosclassic.free_MPDS_IMAGE(input_image_c)

    # Free memory on C side: threshold_c, gamma_c, gammaC_c
    geosclassic.delete_real_array(threshold_c)
    geosclassic.delete_real_array(gamma_c)
    geosclassic.delete_real_array(gammaC_c)
    # geosclassic.MPDSFree(threshold_c)
    # geosclassic.MPDSFree(gamma_c)
    # geosclassic.MPDSFree(gammaC_c)

    return out_array
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def imgConnectivityEulerNumber(
        input_image,
        var_index=0,
        geobody_image_in_input=False,
        complementary_set=False,
        nthreads=-1):
    """
    Computes the Euler number for one variable v of the input image.

    The Euler number is defined, for the 3D image grid, as
    E = number of connected components (geobodies)
        + number of "holes"
        - number of "handles"
    for the set {v>0}, i.e. the indicator variable I(x) = 1 iff v(x)>0, is
    considered.
    The Euler number E can be computed by the formula:
    E = sum_{i=1,...,N} (e0(i) - e1(i) + e2(i) - e3(i)),
    where
        - N the number of connected component (geobodies) in the set {I=1}
        - for a geobody i:
            - e0(i) : the number of vertices (dim 0) in the i-th geobody
            - e1(i) : the number of edges (dim 1) in the i-th geobody
            - e2(i) : the number of faces (dim 2) in the i-th geobody
            - e3(i) : the number of volumes (dim 3) in the i-th geobody
        where vertices, edges, faces, and volumes of each grid cell
        (3D parallelepiped element) are considered.

    Note that the connected components are computed considering two cells as
    adjacent as soon as they have a common face (`connect_type='connect_face'`
    for the computation of the geobody image (see function `imgGeobodyImage`).

    Parameters
    ----------
    input_image : :class:`geone.img.Img`
        input image
    var_index : int, default: 0
        index of the considered variable in input image
    geobody_image_in_input : bool, default: False
        - if True: the input image is already a geobody image (variable
        `var_index` is the geobody label); in this case the parameter
        `complementary_set` is not used
        - False: the geobody image for the indicator variable {v>0} (with v
        the variable of index `var_index`) is computed
    complementary_set : bool, default: False
        - if True: the complementary indicator variable (IC = 1-I, see above) is
        used
        - if False: the indicator variable I (see above) is used
    nthreads : int, default: -1
        number of thread(s) to use for C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)

    Returns
    -------
    euler_number : float
        Euler number (see above)

    Notes
    -----
    See reference:
    - Renard P, Allard D (2013), Connectivity metrics for subsurface flow and
    transport. Adv Water Resour 51:168–196.
    https://doi.org/10.1016/j.advwatres.2011.12.001
    """
    fname = 'imgConnectivityEulerNumber'

    # --- Check and prepare
    if var_index < 0 or var_index >= input_image.nv:
        print(f"ERROR ({fname}): `var_index` not valid")
        return None

    # Compute geobody image
    if not geobody_image_in_input:
        im_geobody = imgGeobodyImage(input_image,
                                     var_index,
                                     bound_inf=0.0,
                                     bound_sup=None,
                                     bound_inf_excluded=True,
                                     bound_sup_excluded=True,
                                     complementary_set=complementary_set,
                                     connect_type='connect_face')
        iv = 0
    else:
        im_geobody = input_image
        iv = var_index

    # Compute Euler Number
    if im_geobody is not None:
        # Set geobody image "in C"
        im_geobody_c = img_py2C(im_geobody)

        # Allocate euler number "in C"
        euler_number_c = geosclassic.new_int_array(1)

        # --- Set number of threads
        if nthreads <= 0:
            nth = max(os.cpu_count() + nthreads, 1)
        else:
            nth = nthreads

        # Compute Euler number (launch C code)
        err = geosclassic.MPDSOMPImageConnectivityEulerNumber(im_geobody_c, var_index, euler_number_c, nth)

        # --- Retrieve output "in python"
        if err:
            err_message = geosclassic.mpds_get_error_message(-err)
            err_message = err_message.replace('\n', '')
            print(err_message)
            euler_number = None
        else:
            euler_number = np.zeros(1, dtype='intc') # 'intc' for C-compatibility
            geosclassic.mpds_get_array_from_int_vector(euler_number_c, 0, euler_number)
            euler_number = euler_number[0]

        # Free memory on C side: im_geobody_c
        geosclassic.MPDSFreeImage(im_geobody_c)
        #geosclassic.MPDSFree(im_geobody_c)
        geosclassic.free_MPDS_IMAGE(im_geobody_c)

        # Free memory on C side: euler_number_c
        geosclassic.delete_int_array(euler_number_c)
        # geosclassic.MPDSFree(euler_number_c)

    else:
        return None

    return euler_number
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
def imgConnectivityEulerNumberCurves(
        input_image,
        threshold_min=None,
        threshold_max=None,
        nthreshold=50,
        show_progress=False,
        nthreads=-1):
    """
    Computes the curves of Euler number for one variable v of the input image.

    For a threshold t:
    - we consider the indicator variable I(t) defined as
    I(t)(x) = 1 iif v(x) <= t
    - we compute the Euler number
    E(t) = number of connected components (geobodies)
        + number of "holes"
        - number of "handles",
    for the set {I(t)=1}
    - we compute also EC(t), the Euler number for the complementary set
    {IC(t)=1} where IC(t)(x) = 1 - I(t)(x)
    This is repeated for different threshold values t, which gives the curves
    of Euler numbers E(t) and EC(t).
    See function `imgConnectivityEulerNumber` for details about Euler number.

    Note that the connected components are computed considering two cells as
    adjacent as soon as they have a common face (`connect_type='connect_face'`
    for the computation of the geobody image (see function `imgGeobodyImage`).

    Parameters
    ----------
    input_image : :class:`geone.img.Img`
        input image, it should have only one variable
    threshold_min : float, optional
        minimal value of the threshold;
        by default (`None`): min of the input variable values minus 1.e-10
    threshold_max : float, optional
        maximal value of the threshold;
        by default (`None`): max of the input variable values plus 1.e-10
    nthreshod : int, default: 50
        number of thresholds considered, the threshold values are
        `numpy.linspace(threshold_min, threshold_max, nthreshold)`
    show_progress : bool, default: False
        indicates if progress is displayed (True) or not (False)
    nthreads : int, default: -1
        number of thread(s) to use for C program;
        `nthreads = -n <= 0`: maximal number of threads of the system except n
        (but at least 1)

    Returns
    -------
    out_array : 2D array of floats of shape (ntrheshold, 3)
        the columns correspond to: the threshold values, the Euler numbers E,
        and the Euler numbers EC, i.e.:
        - `out_array[i, 0]`:
        `numpy.linspace(threshold_min, threshold_max, nthreshold)`
        - `out_array[i, 1]`: E(out_array[i, 0])
        - `out_array[i, 2]`: EC(out_array[i, 0])
    """
    fname = 'imgConnectivityEulerNumberCurves'

    # --- Check and prepare
    if input_image.nv != 1:
        print(f'ERROR ({fname}): input image must have one variable only')
        return None

    if threshold_min is None:
        threshold_min = np.nanmin(input_image.val) - 1.e-10

    if threshold_max is None:
        threshold_max = np.nanmax(input_image.val) + 1.e-10

    if threshold_min > threshold_max:
        print(f"ERROR ({fname}): `threshold_min` is greater than `threshold_max`")
        return None

    if nthreshold < 0:
        print(f"ERROR ({fname}): `nthreshold` is negative")
        return None
    elif nthreshold == 1:
        threshold_step = 1.0
    else:
        threshold_step = (threshold_max - threshold_min) / (nthreshold - 1)

    if threshold_step < geosclassic.MPDS_EPSILON:
        print(f'ERROR ({fname}): threshold step too small')
        return None

    # Set input image "in C"
    input_image_c = img_py2C(input_image)

    # Allocate output variable in C
    threshold_c = geosclassic.new_real_array(nthreshold)
    euler_number_c = geosclassic.new_int_array(nthreshold)
    euler_numberC_c = geosclassic.new_int_array(nthreshold)

    # --- Set number of threads
    if nthreads <= 0:
        nth = max(os.cpu_count() + nthreads, 1)
    else:
        nth = nthreads

    # --- Compute Euler number curves (launch C code)
    err = geosclassic.MPDSOMPImageConnectivity6EulerNumberCurve(
            input_image_c, nthreshold, threshold_min, threshold_step,
            threshold_c, euler_number_c, euler_numberC_c,
            show_progress, nth)

    # --- Retrieve output "in python"
    if err:
        err_message = geosclassic.mpds_get_error_message(-err)
        err_message = err_message.replace('\n', '')
        print(err_message)
        out_array = None
    else:
        threshold = np.zeros(nthreshold)
        geosclassic.mpds_get_array_from_real_vector(threshold_c, 0, threshold)

        euler_number = np.zeros(nthreshold, dtype='intc') # 'intc' for C-compatibility
        geosclassic.mpds_get_array_from_int_vector(euler_number_c, 0, euler_number)

        euler_numberC = np.zeros(nthreshold, dtype='intc') # 'intc' for C-compatibility
        geosclassic.mpds_get_array_from_int_vector(euler_numberC_c, 0, euler_numberC)

        out_array = np.array((threshold, euler_number, euler_numberC)).reshape(3, -1).T

    # Free memory on C side: input_image_c
    geosclassic.MPDSFreeImage(input_image_c)
    #geosclassic.MPDSFree(input_image_c)
    geosclassic.free_MPDS_IMAGE(input_image_c)

    # Free memory on C side: threshold_c, gamma_c, gammaC_c
    geosclassic.delete_real_array(threshold_c)
    geosclassic.delete_int_array(euler_number_c)
    geosclassic.delete_int_array(euler_numberC_c)
    # geosclassic.MPDSFree(threshold_c)
    # geosclassic.MPDSFree(euler_number_c)
    # geosclassic.MPDSFree(euler_numberC_c)

    return out_array
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    print("Module 'geone.geosclassicinterface'.")
