import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { glob } from 'astro/loaders';

const title = z.string().trim().min(1).max(180);
const optionalText = z.preprocess(
  (value) => value === null || value === '' ? undefined : value,
  z.string().trim().optional(),
);
const optionalUrl = z.preprocess(
  (value) => value === null || value === '' ? undefined : value,
  z.url({ protocol: /^https$/ }).optional(),
);
const localImage = z.string().regex(
  /^\/images\/(?!.*(?:\.\.|\/\/|[?#\\]))[^\s]+\.(?:avif|webp|png|jpe?g|gif)$/i,
  'Use an uploaded image under /images/, never an expiring CDN URL.',
);
const optionalImage = z.preprocess(
  (value) => value === null || value === '' ? undefined : value,
  localImage.optional(),
);
const date = z.preprocess(
  (value) => typeof value === 'string' && value.trim() ? new Date(value) : value,
  z.date(),
);
const draft = z.boolean().default(true);
const images = z.preprocess((value) => value ?? [], z.array(localImage).default([]));
const tags = z.preprocess(
  (value) => value ?? [],
  z.array(z.string().trim().min(1).max(64)).max(40).default([]),
);

const dispatches = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/dispatches' }),
  schema: z.object({
    title,
    dispatchNumber: z.number().int().positive(),
    date,
    source: z.enum(['instagram', 'website']).default('website'),
    instagramId: z.preprocess(
      (value) => value === null || value === '' ? undefined : value,
      z.string().regex(/^\d+$/).optional(),
    ),
    instagramUrl: optionalUrl,
    images,
    imageAlts: z.preprocess((value) => value ?? [], z.array(z.string()).default([])),
    captionExcerpt: z.string().trim().max(360).default(''),
    location: z.string().trim().default(''),
    tags,
    featured: z.boolean().default(false),
    draft,
    lockedForManualEdits: z.boolean().default(true),
  }).strict().superRefine((data, ctx) => {
    if (data.source === 'instagram' && (!data.instagramId || !data.instagramUrl)) {
      ctx.addIssue({ code: 'custom', message: 'Instagram dispatches require instagramId and instagramUrl.' });
    }
    if (data.imageAlts.length && data.imageAlts.length !== data.images.length) {
      ctx.addIssue({ code: 'custom', path: ['imageAlts'], message: 'Provide one alt description per image, or leave this list empty.' });
    }
  }),
});

const works = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/works' }),
  schema: z.object({
    title,
    subtitle: optionalText,
    date,
    category: z.enum(['essay', 'poetry', 'short-story', 'reflection']),
    readingTime: z.number().int().min(1).max(600),
    featured: z.boolean().default(false),
    draft,
    coverImage: optionalImage,
    coverAlt: optionalText,
  }).strict(),
});

const book = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/book' }),
  schema: z.object({
    title,
    subtitle: optionalText,
    date,
    kind: z.enum(['overview', 'excerpt']),
    synopsis: z.string().trim().min(1).max(5000),
    status: z.enum(['gathering-stories', 'drafting', 'revising', 'seeking-publication', 'published']),
    progress: z.number().int().min(0).max(100).default(0),
    thematicPillars: z.preprocess((value) => value ?? [], z.array(z.string().trim().min(1)).max(12).default([])),
    order: z.number().int().min(0).default(0),
    chapterNumber: z.preprocess((value) => value === null || value === '' ? undefined : value, z.number().int().positive().optional()),
    draft,
    coverImage: optionalImage,
    coverAlt: optionalText,
  }).strict().superRefine((data, ctx) => {
    if (data.kind === 'excerpt' && !data.chapterNumber) {
      ctx.addIssue({ code: 'custom', path: ['chapterNumber'], message: 'Excerpts require a positive chapter number.' });
    }
  }),
});

const events = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/events' }),
  schema: z.object({
    type: z.enum(['upcoming-event', 'past-event', 'award', 'publication', 'milestone']),
    title,
    date,
    location: z.string().trim().default(''),
    organization: z.string().trim().default(''),
    description: z.string().trim().min(1).max(2000),
    externalUrl: optionalUrl,
    photos: images,
    photoAlts: z.preprocess((value) => value ?? [], z.array(z.string()).default([])),
    draft,
  }).strict(),
});

export const collections = { dispatches, works, book, events };
