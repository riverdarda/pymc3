import numpy as np
import pymc3 as pm
from pymc3 import Model, Normal, DiscreteUniform, Poisson, switch, Exponential
from pymc3.theanof import inputvars
from pymc3.variational import advi, advi_minibatch, sample_vp
from pymc3.variational.advi import _calc_elbo, adagrad_optimizer
from pymc3.theanof import CallableTensor
from theano import function, shared
import theano.tensor as tt

from nose.tools import assert_raises


def test_elbo():
    mu0 = 1.5
    sigma = 1.0
    y_obs = np.array([1.6, 1.4])

    # Create a model for test
    with Model() as model:
        mu = Normal('mu', mu=mu0, sd=sigma)
        Normal('y', mu=mu, sd=1, observed=y_obs)

    vars = inputvars(model.vars)

    # Create variational gradient tensor
    elbo, _ = _calc_elbo(vars, model, n_mcsamples=10000, random_seed=1)

    # Variational posterior parameters
    uw_ = np.array([1.88, np.log(1)])

    # Calculate elbo computed with MonteCarlo
    uw_shared = shared(uw_, 'uw_shared')
    elbo = CallableTensor(elbo)(uw_shared)
    f = function([], elbo)
    elbo_mc = f()

    # Exact value
    elbo_true = (-0.5 * (
        3 + 3 * uw_[0]**2 - 2 * (y_obs[0] + y_obs[1] + mu0) * uw_[0] +
        y_obs[0]**2 + y_obs[1]**2 + mu0**2 + 3 * np.log(2 * np.pi)) +
        0.5 * (np.log(2 * np.pi) + 1))

    np.testing.assert_allclose(elbo_mc, elbo_true, rtol=0, atol=1e-1)

disaster_data = np.ma.masked_values([4, 5, 4, 0, 1, 4, 3, 4, 0, 6, 3, 3, 4, 0, 2, 6,
                                     3, 3, 5, 4, 5, 3, 1, 4, 4, 1, 5, 5, 3, 4, 2, 5,
                                     2, 2, 3, 4, 2, 1, 3, -999, 2, 1, 1, 1, 1, 3, 0, 0,
                                     1, 0, 1, 1, 0, 0, 3, 1, 0, 3, 2, 2, 0, 1, 1, 1,
                                     0, 1, 0, 1, 0, 0, 0, 2, 1, 0, 0, 0, 1, 1, 0, 2,
                                     3, 3, 1, -999, 2, 1, 1, 1, 1, 2, 4, 2, 0, 0, 1, 4,
                                     0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1], value=-999)
year = np.arange(1851, 1962)


def test_check_discrete():
    with Model() as disaster_model:
        switchpoint = DiscreteUniform(
            'switchpoint', lower=year.min(), upper=year.max(), testval=1900)

        # Priors for pre- and post-switch rates number of disasters
        early_rate = Exponential('early_rate', 1)
        late_rate = Exponential('late_rate', 1)

        # Allocate appropriate Poisson rates to years before and after current
        rate = switch(switchpoint >= year, early_rate, late_rate)
        Poisson('disasters', rate, observed=disaster_data)

    # This should raise ValueError
    assert_raises(ValueError, advi, model=disaster_model, n=10)


def test_check_discrete_minibatch():
    disaster_data_t = tt.vector()
    disaster_data_t.tag.test_value = np.zeros(len(disaster_data))

    with Model() as disaster_model:

        switchpoint = DiscreteUniform(
            'switchpoint', lower=year.min(), upper=year.max(), testval=1900)

        # Priors for pre- and post-switch rates number of disasters
        early_rate = Exponential('early_rate', 1)
        late_rate = Exponential('late_rate', 1)

        # Allocate appropriate Poisson rates to years before and after current
        rate = switch(switchpoint >= year, early_rate, late_rate)

        disasters = Poisson('disasters', rate, observed=disaster_data_t)

    def create_minibatch():
        while True:
            return (disaster_data,)

    # This should raise ValueError
    assert_raises(
        ValueError, advi_minibatch, model=disaster_model, n=10,
        minibatch_RVs=[disasters], minibatch_tensors=[disaster_data_t],
        minibatches=create_minibatch(), verbose=False)


def test_advi():
    n = 1000
    sd0 = 2.
    mu0 = 4.
    sd = 3.
    mu = -5.

    data = sd * np.random.RandomState(0).randn(n) + mu

    d = n / sd**2 + 1 / sd0**2
    mu_post = (n * np.mean(data) / sd**2 + mu0 / sd0**2) / d

    with Model() as model:
        mu_ = Normal('mu', mu=mu0, sd=sd0, testval=0)
        Normal('x', mu=mu_, sd=sd, observed=data)

    advi_fit = advi(
        model=model, n=1000, accurate_elbo=False, learning_rate=1e-1,
        random_seed=1)

    np.testing.assert_allclose(advi_fit.means['mu'], mu_post, rtol=0.1)

    trace = sample_vp(advi_fit, 10000, model)

    np.testing.assert_allclose(np.mean(trace['mu']), mu_post, rtol=0.4)
    np.testing.assert_allclose(np.std(trace['mu']), np.sqrt(1. / d), rtol=0.4)


def test_advi_optimizer():
    n = 1000
    sd0 = 2.
    mu0 = 4.
    sd = 3.
    mu = -5.

    data = sd * np.random.RandomState(0).randn(n) + mu

    d = n / sd**2 + 1 / sd0**2
    mu_post = (n * np.mean(data) / sd**2 + mu0 / sd0**2) / d

    with Model() as model:
        mu_ = Normal('mu', mu=mu0, sd=sd0, testval=0)
        Normal('x', mu=mu_, sd=sd, observed=data)

    optimizer = adagrad_optimizer(learning_rate=0.1, epsilon=0.1)
    advi_fit = advi(model=model, n=1000, optimizer=optimizer, random_seed=1)

    np.testing.assert_allclose(advi_fit.means['mu'], mu_post, rtol=0.1)

    trace = sample_vp(advi_fit, 10000, model)

    np.testing.assert_allclose(np.mean(trace['mu']), mu_post, rtol=0.4)
    np.testing.assert_allclose(np.std(trace['mu']), np.sqrt(1. / d), rtol=0.4)


def test_advi_minibatch():
    n = 1000
    sd0 = 2.
    mu0 = 4.
    sd = 3.
    mu = -5.

    data = sd * np.random.RandomState(0).randn(n) + mu

    d = n / sd**2 + 1 / sd0**2
    mu_post = (n * np.mean(data) / sd**2 + mu0 / sd0**2) / d

    data_t = tt.vector()
    data_t.tag.test_value = np.zeros(1,)

    with Model() as model:
        mu_ = Normal('mu', mu=mu0, sd=sd0, testval=0)
        x = Normal('x', mu=mu_, sd=sd, observed=data_t)

    minibatch_RVs = [x]
    minibatch_tensors = [data_t]

    def create_minibatch(data):
        while True:
            data = np.roll(data, 100, axis=0)
            yield (data[:100],)

    minibatches = create_minibatch(data)

    with model:
        advi_fit = advi_minibatch(
            n=1000, minibatch_tensors=minibatch_tensors,
            minibatch_RVs=minibatch_RVs, minibatches=minibatches,
            total_size=n, learning_rate=1e-1, random_seed=1
        )

        np.testing.assert_allclose(advi_fit.means['mu'], mu_post, rtol=0.1)

        trace = sample_vp(advi_fit, 10000)

    np.testing.assert_allclose(np.mean(trace['mu']), mu_post, rtol=0.4)
    np.testing.assert_allclose(np.std(trace['mu']), np.sqrt(1. / d), rtol=0.4)


def test_advi_minibatch_shared():
    n = 1000
    sd0 = 2.
    mu0 = 4.
    sd = 3.
    mu = -5.

    data = sd * np.random.RandomState(0).randn(n) + mu

    d = n / sd**2 + 1 / sd0**2
    mu_post = (n * np.mean(data) / sd**2 + mu0 / sd0**2) / d

    data_t = shared(np.zeros(1,))

    with Model() as model:
        mu_ = Normal('mu', mu=mu0, sd=sd0, testval=0)
        x = Normal('x', mu=mu_, sd=sd, observed=data_t)

    minibatch_RVs = [x]
    minibatch_tensors = [data_t]

    def create_minibatch(data):
        while True:
            data = np.roll(data, 100, axis=0)
            yield (data[:100],)

    minibatches = create_minibatch(data)

    with model:
        advi_fit = advi_minibatch(
            n=1000, minibatch_tensors=minibatch_tensors,
            minibatch_RVs=minibatch_RVs, minibatches=minibatches,
            total_size=n, learning_rate=1e-1, random_seed=1
        )

        np.testing.assert_allclose(advi_fit.means['mu'], mu_post, rtol=0.1)

        trace = sample_vp(advi_fit, 10000)

    np.testing.assert_allclose(np.mean(trace['mu']), mu_post, rtol=0.4)
    np.testing.assert_allclose(np.std(trace['mu']), np.sqrt(1. / d), rtol=0.4)


def test_sample_vp():
    n_samples = 100

    rng = np.random.RandomState(0)
    xs = rng.binomial(n=1, p=0.2, size=n_samples)

    with pm.Model() as model:
        p = pm.Beta('p', alpha=1, beta=1)
        pm.Binomial('xs', n=1, p=p, observed=xs)
        v_params = advi(n=1000)

    with model:
        trace = sample_vp(v_params, hide_transformed=True)
    assert(set(trace.varnames) == set('p'))

    with model:
        trace = sample_vp(v_params, hide_transformed=False)
    assert(set(trace.varnames) == set(('p', 'p_logodds_')))
