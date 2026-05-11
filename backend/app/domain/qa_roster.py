from app.domain.models import FeatureType

QA_ASSIGNEE_BY_FEATURE_TYPE: dict[FeatureType, str] = {
    FeatureType.GAMEPLAY_LOGIC: "Ngoc Anh",
    FeatureType.UI_LAYOUT: "Minh",
    FeatureType.LEVEL_PUZZLE: "Huy",
    FeatureType.ECONOMY: "Linh",
    FeatureType.BACKEND_LIVEOPS: "Quan",
    FeatureType.ANIMATION: "Minh",
    FeatureType.TUTORIAL: "Minh",
    FeatureType.CROSS_CUTTING: "QA Lead",
}

QA_MEMBERS = {
    assignee
    for feature_type, assignee in QA_ASSIGNEE_BY_FEATURE_TYPE.items()
    if feature_type != FeatureType.CROSS_CUTTING
}
