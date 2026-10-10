"""Presentation-only controls for the same-origin Community Cloud wrapper."""
import streamlit as st


def hide_creator_profile() -> None:
    # The creator link is rendered by the hosting page outside the app iframe.
    # Hide only that link; the hosting badge remains visible. The public creator
    # profile still exists, so this is a UI preference rather than access control.
    st.html(
        """<script>
        (() => {
            try {
                const host = window.parent;
                if (!host.location.hostname.endsWith('.streamlit.app')) return;
                const doc = host.document;
                const id = 'steppegrid-hide-creator-profile';
                if (doc.getElementById(id)) return;
                const style = doc.createElement('style');
                style.id = id;
                style.textContent = 'a:has(img[data-testid="appCreatorAvatar"]) { display: none !important; }';
                doc.head.appendChild(style);
            } catch (_) {
                // An unrelated cross-origin embed cannot change its host page.
            }
        })();
        </script>""",
        unsafe_allow_javascript=True,
    )
