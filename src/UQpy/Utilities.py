# UQpy is distributed under the MIT license.
#
# Copyright (C) 2018  -- Michael D. Shields
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats
from contextlib import contextmanager
import sys
import os
from scipy.special import gamma
from scipy.stats import chi2, norm


def _run_parallel_python(model_script, model_object_name, sample, dict_kwargs):
    """
    Execute the python model in parallel
    :param sample: One sample point where the model has to be evaluated
    :return:
    """

    exec('from ' + model_script[:-3] + ' import ' + model_object_name)
    # if kwargs is not None:
    #     par_res = eval(model_object_name + '(sample, kwargs)')
    # else:
    if len(dict_kwargs) == 0:
        par_res = eval(model_object_name + '(sample)')
    else:
        par_res = eval(model_object_name + '(sample, **dict_kwargs)')
    # par_res = parallel_output
    # if self.model_is_class:
    #     par_res = parallel_output.qoi
    # else:
    #     par_res = parallel_output

    return par_res


# def compute_Voronoi_volume(vertices):
#
#     from scipy.spatial import Delaunay
#
#     d = Delaunay(vertices)
#     d_vol = np.zeros(np.size(vertices, 0))
#     for i in range(d.nsimplex):
#         d_verts = vertices[d.simplices[i]]
#         d_vol[i] = compute_Delaunay_volume(d_verts)
#
#     volume = np.sum(d_vol)
#     return volume


def voronoi_unit_hypercube(samples):

    from scipy.spatial import Voronoi, voronoi_plot_2d

    # Mirror the samples in both low and high directions for each dimension
    samples_center = samples
    dimension = samples.shape[1]
    for i in range(dimension):
        samples_del = np.delete(samples_center, i, 1)
        if i == 0:
            points_temp1 = np.hstack([np.atleast_2d(-samples_center[:,i]).T, samples_del])
            points_temp2 = np.hstack([np.atleast_2d(2-samples_center[:,i]).T, samples_del])
        elif i == dimension-1:
            points_temp1 = np.hstack([samples_del, np.atleast_2d(-samples_center[:, i]).T])
            points_temp2 = np.hstack([samples_del, np.atleast_2d(2 - samples_center[:, i]).T])
        else:
            points_temp1 = np.hstack([samples_del[:,:i], np.atleast_2d(-samples_center[:, i]).T, samples_del[:,i:]])
            points_temp2 = np.hstack([samples_del[:,:i], np.atleast_2d(2 - samples_center[:, i]).T, samples_del[:,i:]])
        samples = np.append(samples, points_temp1, axis=0)
        samples = np.append(samples, points_temp2, axis=0)

    vor = Voronoi(samples, incremental=True)

    eps = sys.float_info.epsilon
    regions = [None]*samples_center.shape[0]

    for i in range(samples_center.shape[0]):
        regions[i] = vor.regions[vor.point_region[i]]

    # for region in vor.regions:
    #     flag = True
    #     for index in region:
    #         if index == -1:
    #             flag = False
    #             break
    #         else:
    #             for i in range(dimension):
    #                 x = vor.vertices[index, i]
    #                 if not (-eps <= x and x <= 1 + eps):
    #                     flag = False
    #                     break
    #     if region != [] and flag:
    #         regions.append(region)

    vor.bounded_points = samples_center
    vor.bounded_regions = regions

    return vor


def compute_Voronoi_centroid_volume(vertices):

    from scipy.spatial import Delaunay, ConvexHull

    T = Delaunay(vertices)
    dimension = np.shape(vertices)[1]

    w = np.zeros((T.nsimplex, 1))
    cent = np.zeros((T.nsimplex, dimension))
    for i in range(T.nsimplex):
        ch = ConvexHull(T.points[T.simplices[i]])
        w[i] = ch.volume
        cent[i, :] = np.mean(T.points[T.simplices[i]], axis=0)
    V = np.sum(w)
    C = np.matmul(np.divide(w, V).T, cent)

    return C, V


def compute_Delaunay_centroid_volume(vertices):

    from scipy.spatial import ConvexHull
    import math

    ch = ConvexHull(vertices)
    volume = ch.volume
    centroid = np.mean(vertices, axis=0)

    # v1 = np.concatenate((np.ones([np.size(vertices, 0), 1]), vertices), 1)
    # volume = (1 / math.factorial(np.size(vertices, 0) - 1)) * np.linalg.det(v1.T)

    return centroid, volume


def correlation_distortion(marginal, params, rho_norm):

    """
        Description:

            A function to solve the double integral equation in order to evaluate the modified correlation
            matrix in the standard normal space given the correlation matrix in the original space. This is achieved
            by a quadratic two-dimensional Gauss-Legendre integration.
        Input:
            :param marginal: marginal distributions
            :type marginal: list
            :param params: marginal distribution parameters.
            :type params: list
            :param rho_norm: Correlation at standard normal space.
            :type rho_norm: ndarray
        Output:
            :return rho: Distorted correlation
            :rtype rho: ndarray

    """

    n = 1024
    z_max = 8
    z_min = -z_max
    points, weights = np.polynomial.legendre.leggauss(n)
    points = - (0.5 * (points + 1) * (z_max - z_min) + z_min)
    weights = weights * (0.5 * (z_max - z_min))

    xi = np.tile(points, [n, 1])
    xi = xi.flatten(order='F')
    eta = np.tile(points, n)

    first = np.tile(weights, n)
    first = np.reshape(first, [n, n])
    second = np.transpose(first)

    weights2d = first * second
    w2d = weights2d.flatten()
    rho = np.ones_like(rho_norm)

    print('UQpy: Computing Nataf correlation distortion...')
    for i in range(len(marginal)):
        i_cdf_i = marginal[i].icdf
        moments_i = marginal[i].moments
        mi = moments_i(params[i])
        if not (np.isfinite(mi[0]) and np.isfinite(mi[1])):
            raise RuntimeError("UQpy: The marginal distributions need to have finite mean and variance.")

        for j in range(i + 1, len(marginal)):
            i_cdf_j = marginal[j].icdf
            moments_j = marginal[j].moments
            mj = moments_j(params[j])
            if not (np.isfinite(mj[0]) and np.isfinite(mj[1])):
                raise RuntimeError("UQpy: The marginal distributions need to have finite mean and variance.")

            tmp_f_xi = ((i_cdf_j(stats.norm.cdf(xi[:, np.newaxis]), params[j]) - mj[0]) / np.sqrt(mj[1]))
            tmp_f_eta = ((i_cdf_i(stats.norm.cdf(eta[:, np.newaxis]), params[i]) - mi[0]) / np.sqrt(mi[1]))
            coef = tmp_f_xi * tmp_f_eta * w2d

            rho[i, j] = np.sum(coef * bi_variate_normal_pdf(xi, eta, rho_norm[i, j]))
            rho[j, i] = rho[i, j]

    print('UQpy: Done.')
    return rho


def itam(marginal, params, corr, beta, thresh1, thresh2):

    """
        Description:

            A function to perform the  Iterative Translation Approximation Method;  an iterative scheme for
            upgrading the Gaussian power spectral density function.
            [1] Shields M, Deodatis G, Bocchini P. A simple and efficient methodology to approximate a general
            non-Gaussian  stochastic process by a translation process. Probab Eng Mech 2011;26:511–9.


        Input:
            :param marginal: marginal distributions
            :type marginal: list

            :param params: marginal distribution parameters.
            :type params: list

            :param corr: Non-Gaussian Correlation matrix.
            :type corr: ndarray

            :param beta:  A variable selected to optimize convergence speed and desired accuracy.
            :type beta: int

            :param thresh1: Threshold
            :type thresh1: float

            :param thresh2: Threshold
            :type thresh2: float

        Output:
            :return corr_norm: Gaussian correlation matrix
            :rtype corr_norm: ndarray

    """

    if beta is None:
        beta = 1
    if thresh1 is None:
        thresh1 = 0.0001
    if thresh2 is None:
        thresh2 = 0.01

    # Initial Guess
    corr_norm0 = corr
    corr_norm = np.zeros_like(corr_norm0)
    # Iteration Condition
    error0 = 0.1
    error1 = 100.
    max_iter = 50
    iter_ = 0

    print("UQpy: Initializing Iterative Translation Approximation Method (ITAM)")
    while iter_ < max_iter and error1 > thresh1 and abs(error1-error0)/error0 > thresh2:
        error0 = error1
        corr0 = correlation_distortion(marginal, params, corr_norm0)
        error1 = np.linalg.norm(corr - corr0)

        max_ratio = np.amax(np.ones((len(corr), len(corr))) / abs(corr_norm0))

        corr_norm = np.nan_to_num((corr / corr0)**beta * corr_norm0)

        # Do not allow off-diagonal correlations to equal or exceed one
        corr_norm[corr_norm < -1.0] = (max_ratio + 1) / 2 * corr_norm0[corr_norm < -1.0]
        corr_norm[corr_norm > 1.0] = (max_ratio + 1) / 2 * corr_norm0[corr_norm > 1.0]

        # Iteratively finding the nearest PSD(Qi & Sun, 2006)
        corr_norm = np.array(nearest_psd(corr_norm))

        corr_norm0 = corr_norm.copy()

        iter_ = iter_ + 1

        print(["UQpy: ITAM iteration number ", iter_])
        print(["UQpy: Current error, ", error1])

    print("UQpy: ITAM Done.")
    return corr_norm


def bi_variate_normal_pdf(x1, x2, rho):

    """

        Description:

            A function which evaluates the values of the bi-variate normal probability distribution function.

        Input:
            :param x1: value 1
            :type x1: ndarray

            :param x2: value 2
            :type x2: ndarray

            :param rho: correlation between x1, x2
            :type rho: float

        Output:

    """
    return (1 / (2 * np.pi * np.sqrt(1-rho**2)) *
            np.exp(-1/(2*(1-rho**2)) *
                   (x1**2 - 2 * rho * x1 * x2 + x2**2)))


def _get_a_plus(a):

    """
        Description:

            A supporting function for the nearest_pd function

        Input:
            :param a:A general nd array

        Output:
            :return a_plus: A modified nd array
            :rtype:np.ndarray
    """

    eig_val, eig_vec = np.linalg.eig(a)
    q = np.matrix(eig_vec)
    x_diagonal = np.matrix(np.diag(np.maximum(eig_val, 0)))

    return q * x_diagonal * q.T


def _get_ps(a, w=None):

    """
        Description:

            A supporting function for the nearest_pd function

    """

    w05 = np.matrix(w ** .5)

    return w05.I * _get_a_plus(w05 * a * w05) * w05.I


def _get_pu(a, w=None):

    """
        Description:

            A supporting function for the nearest_pd function

    """

    a_ret = np.array(a.copy())
    a_ret[w > 0] = np.array(w)[w > 0]
    return np.matrix(a_ret)


def nearest_psd(a, nit=10):

    """
        Description:
            A function to compute the nearest positive semi definite matrix of a given matrix

         Input:
            :param a: Input matrix
            :type a: ndarray

            :param nit: Number of iterations to perform (Default=10)
            :type nit: int

        Output:
            :return:
    """

    n = a.shape[0]
    w = np.identity(n)
    # w is the matrix used for the norm (assumed to be Identity matrix here)
    # the algorithm should work for any diagonal W
    delta_s = 0
    y_k = a.copy()
    for k in range(nit):

        r_k = y_k - delta_s
        x_k = _get_ps(r_k, w=w)
        delta_s = x_k - r_k
        y_k = _get_pu(x_k, w=w)

    return y_k


def nearest_pd(a):

    """
        Description:

            Find the nearest positive-definite matrix to input
            A Python/Numpy port of John D'Errico's `nearestSPD` MATLAB code [1], which
            credits [2].
            [1] https://www.mathworks.com/matlabcentral/fileexchange/42885-nearestspd
            [2] N.J. Higham, "Computing a nearest symmetric positive semidefinite
            matrix" (1988): https://doi.org/10.1016/0024-3795(88)90223-6

        Input:
            :param a: Input matrix
            :type a:


        Output:

    """

    b = (a + a.T) / 2
    _, s, v = np.linalg.svd(b)

    h = np.dot(v.T, np.dot(np.diag(s), v))

    a2 = (b + h) / 2

    a3 = (a2 + a2.T) / 2

    if is_pd(a3):
        return a3

    spacing = np.spacing(np.linalg.norm(a))
    # The above is different from [1]. It appears that MATLAB's `chol` Cholesky
    # decomposition will accept matrices with exactly 0-eigenvalue, whereas
    # Numpy's will not. So where [1] uses `eps(mineig)` (where `eps` is Matlab
    # for `np.spacing`), we use the above definition. CAVEAT: our `spacing`
    # will be much larger than [1]'s `eps(mineig)`, since `mineig` is usually on
    # the order of 1e-16, and `eps(1e-16)` is on the order of 1e-34, whereas
    # `spacing` will, for Gaussian random matrices of small dimension, be on
    # other order of 1e-16. In practice, both ways converge, as the unit test
    # below suggests.
    k = 1
    while not is_pd(a3):
        min_eig = np.min(np.real(np.linalg.eigvals(a3)))
        a3 += np.eye(a.shape[0]) * (-min_eig * k**2 + spacing)
        k += 1

    return a3


def is_pd(b):

    """
        Description:

            Returns true when input is positive-definite, via Cholesky decomposition.

        Input:
            :param b: A general matrix

        Output:

    """
    try:
        _ = np.linalg.cholesky(b)
        return True
    except np.linalg.LinAlgError:
        return False


def estimate_psd(samples, nt, t):

    """
        Description: A function to estimate the Power Spectrum of a stochastic process given an ensemble of samples

        Input:
            :param samples: Samples of the stochastic process
            :param nt: Number of time discretisations in the time domain
            :param t: Total simulation time

        Output:
            :return: Power Spectrum
            :rtype: ndarray

    """

    sample_size = nt
    sample_max_time = t
    dt = t / (nt - 1)
    x_w = np.fft.fft(samples, sample_size, axis=1)
    x_w = x_w[:, 0: int(sample_size / 2)]
    m_ps = np.mean(np.absolute(x_w) ** 2 * sample_max_time / sample_size ** 2, axis=0)
    num = int(t / (2 * dt))

    return np.linspace(0, (1 / (2 * dt) - 1 / t), num), m_ps


def S_to_R(S, w, t):

    """
        Description:

            A function to transform the power spectrum to an autocorrelation function

        Input:
            :param s: Power Spectrum of the signal
            :param w: Array of frequency discretisations
            :param t: Array of time discretisations

        Output:
            :return r: Autocorrelation function
            :rtype: ndarray
    """

    dw = w[1] - w[0]
    fac = np.ones(len(w))
    fac[1: len(w) - 1: 2] = 4
    fac[2: len(w) - 2: 2] = 2
    fac = fac * dw / 3
    R = np.zeros(len(t))
    for i in range(len(t)):
        R[i] = 2 * np.dot(fac, S * np.cos(w * t[i]))
    return R


def R_to_S(R, w, t):

    """
        Description: A function to transform the autocorrelation function to a power spectrum


        Input:
            :param r: Autocorrelation function of the signal
            :param w: Array of frequency discretizations
            :param t: Array of time discretizations

        Output:
            :return s: Power Spectrum
            :rtype: ndarray

    """
    dt = t[1] - t[0]
    fac = np.ones(len(t))
    fac[1: len(t) - 1: 2] = 4
    fac[2: len(t) - 2: 2] = 2
    fac = fac * dt / 3
    S = np.zeros(len(w))
    for i in range(len(w)):
        S[i] = 2 / (2 * np.pi) * np.dot(fac, R * np.cos(t * w[i]))
    S[S < 0] = 0
    return S


def R_to_r(R):

    """
        Description: A function to scale down the autocorrelation function to a correlation function


        Input:
            :param R: Autocorrelation function of the signal
        Output:
            :return r: correlation function of the signal
            :rtype: ndarray

    """
    r = R/R[0]
    return r

'''
def gradient_old(sample=None, dimension=None, eps=None,  model_script=None, model_object_name=None, input_template=None,
             var_names=None,
             output_script=None, output_object_name=None, ntasks=None, cores_per_task=None, nodes=None, resume=None,
             verbose=None, model_dir=None, cluster=None, order=None):
    """
         Description: A function to estimate the gradients (1st, 2nd, mixed) of a function using finite differences


         Input:
             :param sample: The sample values at which the gradient of the model will be evaluated. Samples can be
             passed directly as  an array or can be passed through the text file 'UQpy_Samples.txt'.
             If passing samples via text file, set samples = None or do not set the samples input.
             :type sample: ndarray

             :param order: The type of derivatives to calculate (1st order, second order, mixed).
             :type order: str

             :param dimension: Number of random variables.
             :type dimension: int

             :param eps: step for the finite difference.
             :type eps: float

             :param model_script: The filename of the Python script which contains commands to execute the model

             :param model_object_name: The name of the function or class which executes the model

             :param input_template: The name of the template input file which will be used to generate input files for
              each run of the model. Refer documentation for more details.

             :param var_names: A list containing the names of the variables which are present in the template input
              files

             :param output_script: The filename of the Python script which contains the commands to process the output

             :param output_object_name: The name of the function or class which has the output values. If the object
              is a class named cls, the output must be saved as cls.qoi. If it a function, it should return the output
              quantity of interest

             :param ntasks: Number of tasks to be run in parallel. RunModel uses GNU parallel to execute models which
              require an input template

             :param cores_per_task: Number of cores to be used by each task

             :param nodes: On MARCC, each node has 24 cores_per_task. Specify the number of nodes if more than one
              node is required.

             :param resume: This option can be set to True if a parallel execution of a model with input template
              failed to finish running all jobs. GNU parallel will then run only the jobs which failed to execute.

             :param verbose: This option can be set to False if you do not want RunModel to print status messages to
              the screen during execution. It is True by default.

             :param model_dir: The directory  that contains the Python script which contains commands to execute the
             model

             :param cluster: This option defines if we run the code into a cluster

         Output:
             :return du_dj: vector of first-order gradients
             :rtype: ndarray
             :return d2u_dj: vector of second-order gradients
             :rtype: ndarray
             :return d2u_dij: vector of mixed gradients
             :rtype: ndarray
     """

    from UQpy.RunModel import RunModel

    if order is None:
        raise ValueError('Exit code: Provide type of derivatives: first, second or mixed.')

    if dimension is None:
     raise ValueError('Error: Dimension must be defined')

    if eps is None:
        eps = [0.1]*dimension
    elif isinstance(eps, float):
        eps = [eps] * dimension
    elif isinstance(eps, list):
        if len(eps) != 1 and len(eps) != dimension:
            raise ValueError('Exit code: Inconsistent dimensions.')
        if len(eps) == 1:
            eps = [eps[0]] * dimension

    if order == 'first' or order == 'second':
        du_dj = np.zeros(dimension)
        d2u_dj = np.zeros(dimension)
        for i in range(dimension):
            x_i1_j = np.array(sample)
            x_i1_j[0, i] += eps[i]
            x_1i_j = np.array(sample)
            x_1i_j[0, i] -= eps[i]

            g0 = RunModel(samples=x_i1_j,  model_script=model_script,
                          model_object_name=model_object_name,
                          input_template=input_template, var_names=var_names, output_script=output_script,
                          output_object_name=output_object_name,
                          ntasks=ntasks, cores_per_task=cores_per_task, nodes=nodes, resume=resume,
                          verbose=verbose, model_dir=model_dir, cluster=cluster)

            g1 = RunModel(samples=x_1i_j,  model_script=model_script,
                          model_object_name=model_object_name,
                          input_template=input_template, var_names=var_names, output_script=output_script,
                          output_object_name=output_object_name,
                          ntasks=ntasks, cores_per_task=cores_per_task, nodes=nodes, resume=resume,
                          verbose=verbose, model_dir=model_dir, cluster=cluster)

            du_dj[i] = (g0.qoi_list[0] - g1.qoi_list[0])/(2*eps[i])

            if order == 'second':
                g = RunModel(samples=sample, model_script=model_script,
                             model_object_name=model_object_name,
                             input_template=input_template, var_names=var_names, output_script=output_script,
                             output_object_name=output_object_name,
                             ntasks=ntasks, cores_per_task=cores_per_task, nodes=nodes, resume=resume,
                             verbose=verbose, model_dir=model_dir, cluster=cluster)

                d2u_dj[i] = (g0.qoi_list[0] - 2 * g.qoi_list[0] + g1.qoi_list[0]) / (eps[i]**2)

        return np.vstack([du_dj, d2u_dj])

    elif order == 'mixed':
        import itertools
        range_ = list(range(dimension))
        d2u_dij = list()
        for i in itertools.combinations(range_, 2):
            x_i1_j1 = np.array(sample)
            x_i1_1j = np.array(sample)
            x_1i_j1 = np.array(sample)
            x_1i_1j = np.array(sample)

            x_i1_j1[0, i[0]] += eps[i[0]]
            x_i1_j1[0, i[1]] += eps[i[1]]

            x_i1_1j[0, i[0]] += eps[i[0]]
            x_i1_1j[0, i[1]] -= eps[i[1]]

            x_1i_j1[0, i[0]] -= eps[i[0]]
            x_1i_j1[0, i[1]] += eps[i[1]]

            x_1i_1j[0, i[0]] -= eps[i[0]]
            x_1i_1j[0, i[1]] -= eps[i[1]]

            g0 = RunModel(samples=x_i1_j1,  model_script=model_script,
                          model_object_name=model_object_name,
                          input_template=input_template, var_names=var_names, output_script=output_script,
                          output_object_name=output_object_name,
                          ntasks=ntasks, cores_per_task=cores_per_task, nodes=nodes, resume=resume,
                          verbose=verbose, model_dir=model_dir, cluster=cluster)

            g1 = RunModel(samples=x_i1_1j,  model_script=model_script,
                          model_object_name=model_object_name,
                          input_template=input_template, var_names=var_names, output_script=output_script,
                          output_object_name=output_object_name,
                          ntasks=ntasks, cores_per_task=cores_per_task, nodes=nodes, resume=resume,
                          verbose=verbose, model_dir=model_dir, cluster=cluster)

            g2 = RunModel(samples=x_1i_j1,  model_script=model_script,
                          model_object_name=model_object_name,
                          input_template=input_template, var_names=var_names, output_script=output_script,
                          output_object_name=output_object_name,
                          ntasks=ntasks, cores_per_task=cores_per_task, nodes=nodes, resume=resume,
                          verbose=verbose, model_dir=model_dir, cluster=cluster)

            g3 = RunModel(samples=x_1i_1j,  model_script=model_script,
                          model_object_name=model_object_name,
                          input_template=input_template, var_names=var_names, output_script=output_script,
                          output_object_name=output_object_name,
                          ntasks=ntasks, cores_per_task=cores_per_task, nodes=nodes, resume=resume,
                          verbose=verbose, model_dir=model_dir, cluster=cluster)

            d2u_dij.append((g0.qoi_list[0] - g1.qoi_list[0] - g2.qoi_list[0] + g3.qoi_list[0])
                           / (4 * eps[i[0]]*eps[i[1]]))

        return np.array(d2u_dij)
'''

'''
def gradient(sample=None, dist_name=None, dist_params=None, model=None, dimension=None, eps=None, order=None,
             corr=None, method=None):

    """
         Description: A function to estimate the gradients (1st, 2nd, mixed) of a function using finite differences

         Input:
             :param sample: The sample values at which the gradient of the model will be evaluated. Samples can be
             passed directly as  an array or can be passed through the text file 'UQpy_Samples.txt'.
             If passing samples via text file, set samples = None or do not set the samples input.
             :type sample: ndarray

             :param dist_name: Probability distribution model for each random variable (see Distributions class).
             :type dist_name: list/string
             :param dist_params: Probability distribution model parameters for each random variable.
                                   (see Distributions class).
             :type dist_params: list
             :param corr: Correlation of the samples
             :type corr: ndarray
             :param order: The type of derivatives to calculate (1st order, second order, mixed).
             :type order: str

             :param dimension: Number of random variables.
             :type dimension: int

             :param method: Finite difference method (Options: Central, backwards, forward).
             :type dimension: int

             :param eps: step for the finite difference.
             :type eps: float

             :param model: An object of type RunModel
             :type model: RunModel object

         Output:
             :return du_dj: vector of first-order gradients
             :rtype: ndarray
             :return d2u_dj: vector of second-order gradients
             :rtype: ndarray
             :return d2u_dij: vector of mixed gradients
             :rtype: ndarray
     """
    from UQpy.Transformations import Nataf
    if order is None:
        raise ValueError('Exit code: Provide type of derivatives: first, second or mixed.')

    if dimension is None:
     raise ValueError('Error: Dimension must be defined')

    if eps is None:
        eps = [0.1]*dimension
    elif isinstance(eps, float):
        eps = [eps] * dimension
    elif isinstance(eps, list):
        if len(eps) != 1 and len(eps) != dimension:
            raise ValueError('Exit code: Inconsistent dimensions.')
        if len(eps) == 1:
            eps = [eps[0]] * dimension

    if model is None:
        raise RuntimeError('A model must be provided.')

    if order == 'first' or order == 'second':
        du_dj = np.zeros(dimension)
        d2u_dj = np.zeros(dimension)
        for ii in range(dimension):
            eps_i = eps[ii] * dist_params[ii][1]
            x_i1_j = np.array(sample)
            x_i1_j[0, ii] = x_i1_j[0, ii] + eps_i
            x_1i_j = np.array(sample)
            x_1i_j[0, ii] = x_1i_j[0, ii] - eps_i

            qoi = model.qoi_list[0]
            if method.lower() == 'Forward':
                model.run(x_i1_j, append_samples=False)
                qoi_plus = model.qoi_list[0]
                du_dj[ii] = (qoi_plus - qoi) / eps_i
            elif method.lower() == 'Backwards':
                model.run(x_1i_j, append_samples=False)
                qoi_minus = model.qoi_list[0]
                du_dj[ii] = (qoi - qoi_minus) / eps_i
            else:
                model.run(x_i1_j, append_samples=False)
                qoi_plus = model.qoi_list[0]
                model.run(x_1i_j, append_samples=False)
                qoi_minus = model.qoi_list[0]
                du_dj[ii] = (qoi_plus - qoi_minus) / (2 * eps_i)
                if order == 'second':
                    d2u_dj[ii] = (qoi_plus - 2 * qoi + qoi_minus) / (eps_i ** 2)

        return np.vstack([du_dj, d2u_dj])

    elif order == 'mixed':
        import itertools
        range_ = list(range(dimension))
        d2u_dij = list()
        for i in itertools.combinations(range_, 2):
            x_i1_j1 = np.array(sample)
            x_i1_1j = np.array(sample)
            x_1i_j1 = np.array(sample)
            x_1i_1j = np.array(sample)

            x_i1_j1[0, i[0]] += eps[i[0]] * dist_params[i[0]][1]
            x_i1_j1[0, i[1]] += eps[i[1]] * dist_params[i[0]][1]

            x_i1_1j[0, i[0]] += eps[i[0]] * dist_params[i[0]][1]
            x_i1_1j[0, i[1]] -= eps[i[1]] * dist_params[i[0]][1]

            x_1i_j1[0, i[0]] -= eps[i[0]] * dist_params[i[0]][1]
            x_1i_j1[0, i[1]] += eps[i[1]] * dist_params[i[0]][1]

            x_1i_1j[0, i[0]] -= eps[i[0]] * dist_params[i[0]][1]
            x_1i_1j[0, i[1]] -= eps[i[1]] * dist_params[i[0]][1]

            model.run(x_i1_j1)
            model.run(x_i1_1j)
            model.run(x_1i_j1)
            model.run(x_1i_1j)

            d2u_dij.append((model.qoi_list[-4] - model.qoi_list[-3] - model.qoi_list[-2] + model.qoi_list[-1])
                           / (4 * eps[i[0]]*eps[i[1]]))

        return np.array(d2u_dij)
'''

def eval_hessian(dimension, mixed_der, der):

    """
    Calculate the hessian matrix with finite differences
    Parameters:

    """
    hessian = np.diag(der)
    import itertools
    range_ = list(range(dimension))
    add_ = 0
    for i in itertools.combinations(range_, 2):
        hessian[i[0], i[1]] = mixed_der[add_]
        hessian[i[1], i[0]] = hessian[i[0], i[1]]
        add_ += 1
    return hessian

def diagnostics(sampling_method, sampling_outputs=None, samples=None, weights=None,
                figsize=None, eps_ESS=0.05, alpha_ESS=0.05):

    """
         Description: A function to estimate the gradients (1st, 2nd, mixed) of a function using finite differences


         Input:
             :param sampling_method: sampling method used to generate samples
             :type sampling_method: str, 'MCMC' or 'IS'

             :param sampling_outputs: output object of a sampling method
             :type sampling_outputs: object of class MCMC or IS

             :param samples: output samples of a sampling method (alternative to giving sampling_outputs for MCMC)
             :type samples: ndarray

             :param weights: output weights of IS (alternative to giving sampling_outputs for IS)
             :type weights: ndarray

             :param figsize: size of the figure for output plots
             :type figsize: tuple (width, height)

             :param eps_ESS: small number required to compute ESS when sampling_method='MCMC', see documentation
             :type eps_ESS: float in [0,1]

             :param alpha_ESS: small number required to compute ESS when sampling_method='MCMC', see documentation
             :type alpha_ESS: float in [0,1]

         Output:
             returns various diagnostics values/plots to evaluate importance sampling and MCMC sampling outputs
     """

    if (eps_ESS < 0) or (eps_ESS > 1):
        raise ValueError('UQpy error: eps_ESS should be a float between 0 and 1.')
    if (alpha_ESS < 0) or (alpha_ESS > 1):
        raise ValueError('UQpy error: alpha_ESS should be a float between 0 and 1.')

    if sampling_method == 'IS':
        if (sampling_outputs is None) and (weights is None):
            raise ValueError('UQpy error: sampling_outputs or weights should be provided')
        if sampling_outputs is not None:
            weights = sampling_outputs.weights
        print('Diagnostics for Importance Sampling \n')
        effective_sample_size = 1/np.sum(weights**2, axis=0)
        print('Effective sample size is ne={}, out of a total number of samples={} \n'.
              format(effective_sample_size,np.size(weights)))
        print('max_weight = {}, min_weight = {} \n'.format(max(weights), min(weights)))

        # Output plots
        if figsize is None:
            figsize = (8, 3)
        fig, ax = plt.subplots(figsize=figsize)
        ax.scatter(weights, np.zeros((np.size(weights), )), s=weights*300, marker='o')
        ax.set_xlabel('weights')
        ax.set_title('Normalized weights out of importance sampling')
        plt.show(fig)

    elif sampling_method == 'MCMC':
        if (sampling_outputs is None) and (samples is None):
            raise ValueError('UQpy error: sampling_outputs or samples should be provided')
        if sampling_outputs is not None:
            samples = sampling_outputs.samples
        print('Diagnostics for MCMC \n')
        nsamples, nparams = samples.shape

        # Acceptance ratio
        if sampling_outputs is not None:
            print('Acceptance ratio of the chain = {}. \n'.format(sampling_outputs.accept_ratio))

        # Computation of ESS and min ESS
        eps = eps_ESS
        alpha = alpha_ESS

        bn = np.ceil(nsamples**(1/2)) # nb of samples per bin
        an = int(np.ceil(nsamples/bn)) # nb of bins, for computation of
        idx = np.array_split(np.arange(nsamples), an)

        means_subdivisions = np.empty((an, samples.shape[1]))
        for i, idx_i in enumerate(idx):
            x_sub = samples[idx_i, :]
            means_subdivisions[i,:] = np.mean(x_sub, axis=0)
        Omega = np.cov(samples.T)
        Sigma = np.cov(means_subdivisions.T)
        joint_ESS = nsamples*np.linalg.det(Omega)**(1/nparams)/np.linalg.det(Sigma)**(1/nparams)
        chi2_value = chi2.ppf(1 - alpha, df=nparams)
        min_joint_ESS = 2 ** (2 / nparams) * np.pi / (nparams * gamma(nparams / 2)) ** (
                    2 / nparams) * chi2_value / eps ** 2
        marginal_ESS = np.empty((nparams, ))
        min_marginal_ESS = np.empty((nparams,))
        for j in range(nparams):
            marginal_ESS[j] = nsamples * Omega[j,j]/Sigma[j,j]
            min_marginal_ESS[j] = 4 * norm.ppf(alpha/2)**2 / eps**2

        print('Univariate Effective Sample Size in each dimension:')
        for j in range(nparams):
            print('Parameter # {}: ESS = {}, minimum ESS recommended = {}'.
                  format(j+1, marginal_ESS[j], min_marginal_ESS[j]))
        print('\nMultivariate Effective Sample Size:')
        print('Multivariate ESS = {}, minimum ESS recommended = {}'.format(joint_ESS, min_joint_ESS))

        # Output plots
        if figsize is None:
            figsize = (20,4*nparams)
        fig, ax = plt.subplots(nrows=nparams, ncols=3, figsize=figsize)
        for j in range(samples.shape[1]):
            ax[j, 0].plot(np.arange(nsamples), samples[:,j])
            ax[j, 0].set_title('chain - parameter # {}'.format(j+1))
            ax[j, 1].plot(np.arange(nsamples), np.cumsum(samples[:,j])/np.arange(nsamples))
            ax[j, 1].set_title('parameter convergence')
            ax[j, 2].acorr(samples[:,j]-np.mean(samples[:,j]), maxlags = 50, normed=True)
            ax[j, 2].set_title('correlation between samples')
        plt.show(fig)

    else:
        raise ValueError('Supported sampling methods for diagnostics are "MCMC", "IS".')
    return fig, ax


def resample(samples, weights, method='multinomial', size=None):
    nsamples = samples.shape[0]
    if size is None:
        size = nsamples
    if method == 'multinomial':
        multinomial_run = np.random.multinomial(size, weights, size=1)[0]
        idx = list()
        for j in range(nsamples):
            if multinomial_run[j] > 0:
                idx.extend([j for _ in range(multinomial_run[j])])
        output = samples[idx, :]
        return output
    else:
        raise ValueError('Exit code: Current available method: multinomial')


@contextmanager
def suppress_stdout():
    """ A function to suppress output"""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout


def check_input_dims(x):
    if not isinstance(x, np.ndarray):
        try:
            x = np.array(x)
        except:
            raise TypeError('Input should be provided as a nested list of 2d ndarray of shape (nsamples, dimension).')
    if len(x.shape) != 2:
        raise TypeError('Input should be provided as a nested list of 2d ndarray of shape (nsamples, dimension).')
    return x


def recursive_update_mean_covariance(n_new, new_sample, previous_mean, previous_covariance=None):
    """ Iterative formula to compute a new mean, covariance based on previous ones and new sample. """
    new_mean = (n_new - 1) / n_new * previous_mean + 1 / n_new * new_sample
    if previous_covariance is None:
        return new_mean
    dim = new_sample.size
    if n_new == 1:
        new_covariance = np.zeros((dim, dim))
    else:
        delta_n = (new_sample - previous_mean).reshape((dim, 1))
        new_covariance = (n_new - 2) / (n_new - 1) * previous_covariance + 1 / n_new * np.matmul(delta_n, delta_n.T)
    return new_mean, new_covariance
