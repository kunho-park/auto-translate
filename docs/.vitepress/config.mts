import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "Auto-Translate Docs",
  description: "Official documentation for the Auto-Translate project.",

  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Guide', link: '/HOW_TO_USE' },
      { text: 'Examples', link: '/markdown-examples' }
    ],

    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'How to Use', link: '/HOW_TO_USE' },
        ]
      },
      {
        text: 'Examples',
        items: [
          { text: 'Markdown Examples', link: '/markdown-examples' },
          { text: 'API Examples', link: '/api-examples' }
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/kunho-park/auto-translate' }
    ]
  },

  locales: {
    root: {
      label: 'English',
      lang: 'en',
      link: '/en/'
    },
    ko: {
      label: '한국어',
      lang: 'ko',
      link: '/ko/',

      themeConfig: {
        nav: [
          { text: '홈', link: '/ko/' },
          { text: '가이드', link: '/ko/guide' }
        ],
        sidebar: [
          {
            text: '사용자 가이드',
            items: [
              { text: '상세 이용 가이드', link: '/ko/guide' }
            ]
          }
        ],
        docFooter: {
          prev: '이전 페이지',
          next: '다음 페이지'
        },
        outlineTitle: '현재 페이지'
      }
    }
  }
})
