bl_info = {
    "name": "Auto Reload Scripts",
    "author": "AceOf3D",
    "version": (1, 0, 1),
    "blender": (4, 5, 1),
    "location": "Text Editor Sidebar (Ctrl+t) > 'Text' tab / Text Editor Toolbar > 'Text' dropdown menu ",
    "description": (
        "Auto reload from disk (ignore local changes) for python scripts in the text editor "
        "whenever the resolve conflict warning appears. Editable options for reload interval "
        "and run after reload in the text editor."
    ),
    "warning": "",
    "wiki_url": "",
    "category": "Scripting",
}

import bpy  # type: ignore
from bpy.app.handlers import persistent  # type: ignore  # added for persistent timer registration
from bpy.props import FloatProperty, BoolProperty  # type: ignore

# default reload interval in seconds (used before UI value is available)
DEFAULT_CHECK_INTERVAL = 0.5

# property names
PROP_INTERVAL = "ars_check_interval"
PROP_RUN_SCRIPT = "ars_run_after_reload"

@persistent
def auto_reload_scripts_timer():
    """Reload python text blocks that were modified externally"""

    def find_text_editor():
        """Return an (window, area, region) trio for the first visible Text Editor, or None."""
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'TEXT_EDITOR':
                    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                    if region is not None:
                        return window, area, region
        return None

    # get current interval from scene property if available and accessible
    if hasattr(bpy.context, "scene") and bpy.context.scene is not None:
        interval_prop = getattr(bpy.context.scene, PROP_INTERVAL, DEFAULT_CHECK_INTERVAL)
    else:
        interval_prop = DEFAULT_CHECK_INTERVAL

    editor_ctx = find_text_editor()
    if editor_ctx is None:
        # No text editor open – skip this cycle
        return interval_prop

    window, area, region = editor_ctx

    for text in bpy.data.texts:
        # only target texts that are linked to a file and flagged as externally modified
        if text.filepath and text.filepath.lower().endswith('.py') and text.is_modified:
            try:
                override = {
                    "window": window,
                    "area": area,
                    "region": region,
                    "edit_text": text,
                }
                with bpy.context.temp_override(**override):
                    bpy.ops.text.reload()

                    # optionally run the script after reload
                    if hasattr(bpy.context, "scene") and bpy.context.scene is not None:
                        if getattr(bpy.context.scene, PROP_RUN_SCRIPT, False):
                            try:
                                bpy.ops.text.run_script()
                                print(f"AutoReloadScripts: executed {text.name}")
                            except Exception as exc_run:
                                print(f"AutoReloadScripts: failed to execute {text.name}: {exc_run}")

                print(f"AutoReloadScripts: reloaded {text.name}")
            except Exception as exc:
                print(f"AutoReloadScripts: failed to reload {text.name}: {exc}")

    # run again after interval
    return interval_prop


# ---------------------- Registration ----------------------


def register():
    """Register UI panel, scene property, and timer."""
    from bpy.utils import register_class # type: ignore

    # Classes to register (UI panel etc.)
    classes_to_register = (ARS_PT_ReloadPanel,)

    for cls in classes_to_register:
        register_class(cls)

    # Scene property for user-configurable interval
    if not hasattr(bpy.types.Scene, PROP_INTERVAL):
        bpy.types.Scene.ars_check_interval = FloatProperty(
            name="Reload Interval (s)",
            description="How often to poll and reload externally-modified scripts",
            min=0.1,
            max=60.0,
            default=DEFAULT_CHECK_INTERVAL,
            step=0.1,
            precision=2,
        )

    # Use default interval when context.scene is unavailable (e.g. during installation)
    first_interval = DEFAULT_CHECK_INTERVAL
    if hasattr(bpy.context, "scene") and bpy.context.scene is not None:
        first_interval = getattr(bpy.context.scene, PROP_INTERVAL, DEFAULT_CHECK_INTERVAL)

    # Register timer (re-registering is harmless; Blender will replace existing entry)
    bpy.app.timers.register(
        auto_reload_scripts_timer,
        first_interval=first_interval,
        persistent=True,
    )

    # add menu to Text Editor dropdown (Text → ...)
    bpy.types.TEXT_MT_text.append(ars_text_menu)

    if not hasattr(bpy.types.Scene, PROP_RUN_SCRIPT):
        bpy.types.Scene.ars_run_after_reload = BoolProperty(
            name="Run After Reload (Live Edit Externally)",
            description="Automatically execute the script once it has been reloaded, works similarly to 'Live Edit' in internal Blender text editor",
            default=False,
        )


def unregister():
    """Unregister timer, scene property, and UI panel."""
    from bpy.utils import unregister_class # type: ignore

    # Unregister timer first
    try:
        bpy.app.timers.unregister(auto_reload_scripts_timer)
    except ValueError:
        pass

    # Remove scene property
    if hasattr(bpy.types.Scene, PROP_INTERVAL):
        del bpy.types.Scene.ars_check_interval
    if hasattr(bpy.types.Scene, PROP_RUN_SCRIPT):
        del bpy.types.Scene.ars_run_after_reload

    for cls in reversed(classes_to_register):
        unregister_class(cls)

    # remove menu item
    if hasattr(bpy.types, "TEXT_MT_text"):
        try:
            bpy.types.TEXT_MT_text.remove(ars_text_menu)
        except ValueError:
            pass


if __name__ == "__main__":
    register()


# ---------------------- UI ----------------------


class ARS_PT_ReloadPanel(bpy.types.Panel):
    """Auto Reload Scripts settings"""

    bl_label = "Auto Reload Scripts"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Text'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, PROP_INTERVAL)
        layout.prop(context.scene, PROP_RUN_SCRIPT)


# tuple of classes for easy registration
classes_to_register = (
    ARS_PT_ReloadPanel,
)


# ---------------------- Menu ----------------------


def ars_text_menu(self, context):
    """Add Auto Reload controls to Text → menu."""
    layout = self.layout
    layout.separator()
    layout.label(text="Auto Reload External Scripts:")

    col = layout.column(align=True)
    col.prop(context.scene, PROP_INTERVAL, text="        Reload Interval (s)")
    col.prop(context.scene, PROP_RUN_SCRIPT, text=" Run After Reload (Live Edit Externally)")
