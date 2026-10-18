"""Keep the Soobin pet and its letter visible across macOS Spaces."""

from ctypes import c_void_p


def show_on_all_spaces(widget):
    try:
        import objc
        from AppKit import (
            NSApp,
            NSApplicationActivationPolicyAccessory,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorStationary,
        )

        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        ns_view = objc.objc_object(c_void_p=int(widget.winId()))
        ns_window = ns_view.window()
        if ns_window:
            ns_window.setLevel_(3)
            ns_window.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
                | NSWindowCollectionBehaviorStationary
            )
    except Exception as exc:
        print(f"[soobin] 无法设置跨桌面空间显示：{exc}")
