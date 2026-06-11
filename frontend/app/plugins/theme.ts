export interface ThemeConfig {
  lightPrimary: string;
  lightAccent: string;
  lightSecondary: string;
  lightSuccess: string;
  lightInfo: string;
  lightWarning: string;
  lightError: string;
  darkPrimary: string;
  darkAccent: string;
  darkSecondary: string;
  darkSuccess: string;
  darkInfo: string;
  darkWarning: string;
  darkError: string;
}

let __cachedTheme: ThemeConfig | undefined;

async function fetchTheme(): Promise<ThemeConfig | undefined> {
  const route = "/api/app/about/theme";

  try {
    const response = await fetch(route);
    const data = await response.json();
    return data as ThemeConfig;
  }
  catch {
    return undefined;
  }
}

export default defineNuxtPlugin(async (nuxtApp) => {
  nuxtApp.hook("vuetify:before-create", async ({ vuetifyOptions }) => {
    let theme = __cachedTheme;
    if (!theme) {
      theme = await fetchTheme();
      __cachedTheme = theme;
    }
    vuetifyOptions.theme = {
      defaultTheme: nuxtApp.$config.public.useDark ? "dark" : "light",
      variations: {
        colors: ["primary", "accent", "secondary", "success", "info", "warning", "error", "background"],
        lighten: 3,
        darken: 3,
      },
      themes: {
        // Warm editorial palette — terracotta + herb-green on warm paper.
        // This fork defines the look directly; the legacy API theme is ignored.
        light: {
          dark: false,
          colors: {
            "primary": "#C0573A",
            "accent": "#3F6F6A",
            "secondary": "#5C6B4E",
            "success": "#5E8C61",
            "info": "#3F6F8E",
            "warning": "#C98A2E",
            "error": "#B23A33",
            "background": "#FAF5EE",
            "surface": "#FFFFFF",
            "surface-variant": "#5A5048",
            "on-background": "#2A2521",
            "on-surface": "#2A2521",
          },
        },
        dark: {
          dark: true,
          colors: {
            "primary": "#DB7A54",
            "accent": "#5EA59B",
            "secondary": "#8A9A78",
            "success": "#7CB07E",
            "info": "#6CA0C0",
            "warning": "#E0A94E",
            "error": "#E0685F",
            "background": "#17130F",
            "surface": "#201B16",
            "surface-variant": "#CDBFB0",
            "on-background": "#ECE3D8",
            "on-surface": "#ECE3D8",
          },
        },
      },
    };
  });
});
