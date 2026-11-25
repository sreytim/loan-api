"""Population Stability Index: how far has a feature's distribution moved from the training data?"""
import numpy as np


def psi(reference, current, bins=10):
    """PSI between a reference sample (training) and a current sample (production)."""
    edges = np.quantile(reference, np.linspace(0, 1, bins + 1))  # 10 equal-share bins on the reference
    edges[0], edges[-1] = -np.inf, np.inf                         # catch values outside the training range
    ref = np.histogram(reference, edges)[0] / len(reference)
    cur = np.histogram(current, edges)[0] / len(current)
    ref, cur = np.clip(ref, 1e-6, None), np.clip(cur, 1e-6, None)  # avoid log(0) for empty bins
    return float(np.sum((cur - ref) * np.log(cur / ref)))


if __name__ == "__main__":
    from data import make_data

    train = make_data(n=5000, seed=42).monthly_income_usd
    similar = make_data(n=1000, seed=3).monthly_income_usd                  # a month like training
    fallen = make_data(n=1000, seed=3, income_mean=300).monthly_income_usd  # incomes fall to mean 300
    print(f"PSI training vs similar month:       {psi(train, similar):.3f}  (below 0.1: stable)")
    print(f"PSI training vs incomes at mean 300: {psi(train, fallen):.3f}  (above 0.2: significant shift)")
