import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import type { APIContext } from 'astro';

export async function GET(context: APIContext) {
  const posts = await getCollection('writings', ({ data }) => !data.draft);
  return rss({
    title: 'Kashish Kapoor',
    description: 'Finance writing + a little bit of fitness.',
    site: context.site!,
    items: posts
      .sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf())
      .map(post => ({
        title: post.data.title,
        pubDate: post.data.date,
        link: `/writings/${post.slug}/`,
      })),
  });
}
