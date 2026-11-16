package com.chronoslife.radar

import android.content.Context
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import javax.xml.parsers.DocumentBuilderFactory

// ---------- sezioni scelte dall'utente (salvate sul telefono) ----------
internal data class CustomSection(val title: String, val keywords: List<String>)

internal class SectionStore(ctx: Context) {
    private val p = ctx.getSharedPreferences("radar", Context.MODE_PRIVATE)
    fun all(): List<CustomSection> {
        val a = JSONArray(p.getString("sections", "[]") ?: "[]")
        return (0 until a.length()).map { i ->
            val o = a.getJSONObject(i)
            val k = o.getJSONArray("keywords")
            CustomSection(o.getString("title"), (0 until k.length()).map { k.getString(it) })
        }
    }
    fun save(list: List<CustomSection>) {
        val a = JSONArray()
        list.forEach { s -> a.put(JSONObject().put("title", s.title).put("keywords", JSONArray(s.keywords))) }
        p.edit().putString("sections", a.toString()).apply()
    }
}

// ---------- analisi in diretta dal telefono: fonti gratuite, nessun server ----------
private fun fetchUrl(url: String): String {
    val c = URL(url).openConnection() as HttpURLConnection
    c.connectTimeout = 10000; c.readTimeout = 10000
    c.setRequestProperty("User-Agent", "CronosLifeRadar/0.1")
    try {
        if (c.responseCode != 200) throw java.io.IOException("HTTP ${c.responseCode}")
        return c.inputStream.bufferedReader().use { it.readText() }
    } finally { c.disconnect() }
}

private fun hnCount(kw: String, from: Long, to: Long): Int {
    val q = URLEncoder.encode("\"$kw\"", "UTF-8")
    val f = URLEncoder.encode("created_at_i>=$from,created_at_i<$to", "UTF-8")
    return JSONObject(fetchUrl("https://hn.algolia.com/api/v1/search?query=$q&tags=story&hitsPerPage=0&numericFilters=$f")).getInt("nbHits")
}

internal data class Headline(val title: String, val link: String, val source: String)

private fun newsHeadlines(kw: String): List<Headline> {
    val q = URLEncoder.encode("$kw when:30d", "UTF-8")
    val xml = fetchUrl("https://news.google.com/rss/search?q=$q&hl=it&gl=IT&ceid=IT:it")
    val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(xml.byteInputStream())
    val nodes = doc.getElementsByTagName("item")
    return (0 until minOf(nodes.length, 40)).map { i ->
        val e = nodes.item(i) as org.w3c.dom.Element
        fun t(tag: String): String = e.getElementsByTagName(tag).item(0)?.textContent ?: ""
        Headline(t("title"), t("link"), t("source"))
    }.filter { it.title.isNotBlank() }
}

internal data class KwResult(val keyword: String, val recent: Int, val previous: Int, val publishers: Int, val momentum: Int?)
internal data class Analysis(val results: List<KwResult>, val headlines: List<Headline>, val errors: List<String>)

/** Stessa formula del backend: Momentum = (recenti - precedenti) / totale * 100, solo con >= 5 evidenze e >= 2 fonti. */
internal fun analyze(s: CustomSection): Analysis {
    val now = System.currentTimeMillis() / 1000
    val day = 86400L
    val results = mutableListOf<KwResult>()
    val heads = mutableListOf<Headline>()
    val errs = mutableListOf<String>()
    for (kw in s.keywords.take(6)) {
        var recent = 0; var previous = 0; var hnOk = false
        try {
            recent = hnCount(kw, now - 45 * day, now + 1)
            previous = hnCount(kw, now - 90 * day, now - 45 * day)
            hnOk = true
        } catch (e: Exception) { errs.add("Hacker News: ${e.message}") }
        var publishers = emptySet<String>()
        try {
            val h = newsHeadlines(kw)
            heads.addAll(h.take(5))
            publishers = h.map { it.source }.filter { it.isNotBlank() }.toSet()
        } catch (e: Exception) { errs.add("Google News: ${e.message}") }
        val total = recent + previous
        val sources = (if (hnOk && total > 0) 1 else 0) + publishers.size
        val ok = total >= 5 && sources >= 2
        val m = if (ok) Math.round(100.0 * (recent - previous) / total).toInt() else null
        results.add(KwResult(kw, recent, previous, publishers.size, m))
    }
    return Analysis(results.sortedByDescending { it.momentum ?: -101 }, heads.distinctBy { it.link }.take(10), errs.distinct())
}

// ---------- schermate ----------
@Composable
internal fun SectionsScreen() {
    val ctx = LocalContext.current.applicationContext
    val sstore = remember { SectionStore(ctx) }
    val store = remember { Store(ctx) }
    var list by remember { mutableStateOf(sstore.all()) }
    var open by remember { mutableStateOf<CustomSection?>(null) }
    val current = open
    if (current != null) {
        SectionDetail(current, store, onBack = { open = null }, onDelete = {
            list = list.filter { it != current }; sstore.save(list); open = null
        })
        return
    }
    var title by remember { mutableStateOf("") }
    var kws by remember { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text("Le tue sezioni", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 16.dp)) }
        item {
            Text("Aggiungi un nuovo settore da monitorare: l'app lo analizza subito, con le stesse regole del Radar. " +
                "Gli argomenti funzionano meglio in inglese (la fonte con storico è Hacker News).", style = MaterialTheme.typography.bodySmall)
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(title, { title = it }, label = { Text("Titolo della sezione (es. Biotech)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(kws, { kws = it }, label = { Text("Argomenti, separati da virgola (facoltativo)") }, modifier = Modifier.fillMaxWidth())
                Button(enabled = title.isNotBlank(), onClick = {
                    val t = title.replace(":", " ").trim()
                    if (t.isNotEmpty() && list.none { it.title.equals(t, ignoreCase = true) }) {
                        val k = kws.split(",").map { it.trim() }.filter { it.isNotEmpty() }.ifEmpty { listOf(t) }
                        list = list + CustomSection(t, k.take(6)); sstore.save(list); title = ""; kws = ""
                    }
                }) { Text("Aggiungi sezione") }
            }
        }
        if (list.isEmpty()) item { Text("Nessuna sezione ancora.") }
        items(list) { s ->
            Card(Modifier.fillMaxWidth().clickable { open = s }) {
                Column(Modifier.padding(16.dp)) {
                    Text(s.title, style = MaterialTheme.typography.titleMedium)
                    Text("Argomenti: ${s.keywords.joinToString()}", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        item { Spacer(Modifier.height(16.dp)) }
    }
}

@Composable
private fun SectionDetail(s: CustomSection, store: Store, onBack: () -> Unit, onDelete: () -> Unit) {
    val state by produceState<Result<Analysis>?>(initialValue = null, s) {
        value = withContext(Dispatchers.IO) { runCatching { analyze(s) } }
    }
    val uri = LocalUriHandler.current
    var watch by remember { mutableStateOf(store.watch()) }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                TextButton(onClick = onBack) { Text("← Sezioni") }
                TextButton(onClick = onDelete) { Text("Elimina sezione") }
            }
        }
        item { Text(s.title, style = MaterialTheme.typography.titleLarge) }
        val r = state
        if (r == null) {
            item { CircularProgressIndicator() }
            item { Text("Analisi in corso…", style = MaterialTheme.typography.bodySmall) }
        } else {
            val a = r.getOrNull()
            if (a == null) {
                item { Text("Analisi non riuscita: ${r.exceptionOrNull()?.message ?: "errore"}") }
            } else {
                item { Text("Momentum calcolato su Hacker News (ultimi 90 giorni, metà recente contro metà precedente); titoli da Google News. È un indicatore, non una previsione.", style = MaterialTheme.typography.bodySmall) }
                if (a.errors.isNotEmpty()) item { Text("Alcune fonti non hanno risposto: ${a.errors.joinToString("; ")}", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                items(a.results) { k ->
                    val key = "${s.title}:${k.keyword}"
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                Text(k.keyword, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                                TextButton(onClick = { store.toggle(key); watch = store.watch() }) { Text(if (key in watch) "★" else "☆") }
                            }
                            Text("Momentum: ${k.momentum?.let { if (it > 0) "+$it" else "$it" } ?: "non disponibile (dati insufficienti)"}")
                            Text("Hacker News: ${k.recent} recenti · ${k.previous} precedenti · testate in notizia: ${k.publishers}", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                item { Text("Titoli recenti", style = MaterialTheme.typography.titleMedium) }
                if (a.headlines.isEmpty()) item { Text("Nessun titolo trovato.", style = MaterialTheme.typography.bodySmall) }
                items(a.headlines) { h ->
                    TextButton(onClick = { runCatching { uri.openUri(h.link) } }, contentPadding = PaddingValues(0.dp)) {
                        Text(h.title, maxLines = 3, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        item { Spacer(Modifier.height(16.dp)) }
    }
}
