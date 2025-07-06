import { defineConfig } from 'vitepress'

export default defineConfig({
  // 사이트 기본 정보
  lang: 'ko-KR',
  title: '모드팩 자동 번역 프로젝트 문서',
  description: 'Auto-Translate Modpack Browser 사용자 및 개발자 문서',

  // 다국어 설정
  locales: {
    root: {
      label: '한국어',
      lang: 'ko'
    },
    en: {
      label: 'English',
      lang: 'en',
      link: '/en/'
    }
  },

  themeConfig: {
    nav: [
      { text: '가이드', link: '/guide' },
      { text: 'English', link: '/en/' }
    ],
    sidebar: {
      '/': [
        { text: '소개', link: '/' },
        { text: '설치', link: '/guide#설치' },
        { text: '번역 방법', link: '/guide#번역-방법' },
        { text: '모델 선택', link: '/guide#모델-선택' },
        { text: '적용 방법', link: '/guide#적용-방법' }
      ],
      '/en/': [
        { text: 'Introduction', link: '/en/' }
      ]
    }
  }
}) 