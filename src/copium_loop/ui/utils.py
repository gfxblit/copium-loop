def get_workflow_status_style(status: str) -> dict[str, str]:
    """Returns the visual representation mapping for a workflow status."""
    styles = {
        "success": {"color": "cyan", "suffix": " ✓ SUCCESS"},
        "failed": {"color": "red", "suffix": " ⚠ FAILED"},
        "running": {"color": "yellow", "suffix": ""},
        "idle": {"color": "yellow", "suffix": ""},
    }
    return styles.get(status, {"color": "yellow", "suffix": ""})
