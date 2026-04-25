import torch.nn as nn
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0


def build_model(pretrained: bool = True, dropout: float = 0.3) -> nn.Module:
    weights = EfficientNet_B0_Weights.DEFAULT if pretrained else None
    model = efficientnet_b0(weights=weights)

    in_features = model.classifier[1].in_features  # 1280
    model.classifier = nn.Sequential(
        nn.Dropout(p=dropout),
        nn.Linear(in_features, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(p=dropout * 0.67),
        nn.Linear(256, 1),
    )
    return model


def freeze_backbone(model: nn.Module) -> None:
    for name, param in model.named_parameters():
        if "classifier" not in name:
            param.requires_grad = False


def unfreeze_all(model: nn.Module) -> None:
    for param in model.parameters():
        param.requires_grad = True
