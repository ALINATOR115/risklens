import pandas as pd

rf = pd.read_csv("outputs/rf_feature_importance.csv")
lr = pd.read_csv("outputs/lr_feature_coefficients.csv")

print("RF TOP 10")
print(rf.head(10))
print()

print("LR TOP 10")
print(lr.head(10))