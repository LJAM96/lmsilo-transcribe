import { useMemo } from 'react'

interface WordCloudProps {
  text: string
  maxWords?: number
}

// Common English stopwords to exclude
const STOPWORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
  'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
  'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
  'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 'ought',
  'used', 'it', 'its', "it's", 'this', 'that', 'these', 'those', 'i', 'you',
  'he', 'she', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
  'his', 'our', 'their', 'what', 'which', 'who', 'whom', 'when', 'where',
  'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
  'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
  'too', 'very', 'just', 'also', 'now', 'here', 'there', 'then', 'if', 'else',
  "i'm", "you're", "he's", "she's", "we're", "they're", "i've", "you've",
  "we've", "they've", "i'd", "you'd", "he'd", "she'd", "we'd", "they'd",
  "i'll", "you'll", "he'll", "she'll", "we'll", "they'll", "isn't", "aren't",
  "wasn't", "weren't", "hasn't", "haven't", "hadn't", "doesn't", "don't",
  "didn't", "won't", "wouldn't", "shan't", "shouldn't", "can't", "cannot",
  "couldn't", "mustn't", "let's", "that's", "who's", "what's", "here's",
  "there's", "when's", "where's", "why's", "how's", 'um', 'uh', 'like', 'yeah',
  'okay', 'ok', 'well', 'just', 'really', 'actually', 'basically', 'literally',
])

interface WordData {
  word: string
  count: number
  size: number
}

export default function WordCloud({ text, maxWords = 50 }: WordCloudProps) {
  const words = useMemo<WordData[]>(() => {
    if (!text) return []

    // Tokenize and count
    const wordCounts = new Map<string, number>()
    const tokens = text.toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .split(/\s+/)
      .filter(w => w.length > 2 && !STOPWORDS.has(w))

    for (const word of tokens) {
      wordCounts.set(word, (wordCounts.get(word) || 0) + 1)
    }

    // Sort by count and take top N
    const sorted = Array.from(wordCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxWords)

    if (sorted.length === 0) return []

    // Calculate relative sizes
    const maxCount = sorted[0][1]
    const minCount = sorted[sorted.length - 1][1]
    const range = maxCount - minCount || 1

    return sorted.map(([word, count]) => ({
      word,
      count,
      size: 12 + ((count - minCount) / range) * 24, // 12-36px range
    }))
  }, [text, maxWords])

  if (words.length === 0) {
    return (
      <div className="text-center text-surface-400 py-8">
        Not enough words to generate cloud
      </div>
    )
  }

  // Shuffle words for visual variety
  const shuffled = [...words].sort(() => Math.random() - 0.5)

  return (
    <div className="flex flex-wrap gap-2 justify-center items-center p-4 bg-cream-50 dark:bg-dark-100 rounded-xl">
      {shuffled.map((w, i) => (
        <span
          key={`${w.word}-${i}`}
          className="inline-block px-2 py-1 rounded transition-transform hover:scale-110 cursor-default"
          style={{
            fontSize: `${w.size}px`,
            color: `hsl(${(i * 37) % 360}, 40%, 45%)`,
            opacity: 0.7 + (w.count / words[0].count) * 0.3,
          }}
          title={`${w.word}: ${w.count} occurrences`}
        >
          {w.word}
        </span>
      ))}
    </div>
  )
}
