from app.domain.models import FeatureType

QA_ASSIGNEE_BY_FEATURE_TYPE: dict[FeatureType, str] = {
    FeatureType.GAMEPLAY_LOGIC: "Ngoc Anh",
    FeatureType.UI_LAYOUT: "Minh",
    FeatureType.LEVEL_PUZZLE: "Huy",
    FeatureType.ECONOMY: "Linh",
    FeatureType.BACKEND_LIVEOPS: "Quan",
    FeatureType.ANIMATION: "Minh",
    FeatureType.TUTORIAL: "Minh",
}

QA_MEMBERS = set(QA_ASSIGNEE_BY_FEATURE_TYPE.values())

