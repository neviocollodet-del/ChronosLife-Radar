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

// ---------- rete e archivio locale ----------
internal fun httpGet(path: String): String {
    val c = URL("${BuildConfig.API_BASE_URL}/$path").openConnection() as HttpURLConnection
    c.connectTimeout = 8000; c.readTimeout = 8000
    try {
        if (c.responseCode != 200) throw java.io.IOException(if (c.responseCode == 404) "Dati non ancora pubblicati" else "Server HTTP ${c.responseCode}")
        return c.inputStream.bufferedReader().use { it.readText() }
    } finally { c.disconnect() }
}

internal class Store(ctx: Context) {
    private val p = ctx.getSharedPreferences("radar", Context.MODE_PRIVATE)
    fun watch(): Set<String> = p.getStringSet("watch", emptySet()) ?: emptySet()
    fun toggle(key: String) {
        val w = watch()
        p.edit().putStringSet("watch", HashSet(if (key in w) w - key else w + key)).apply()
    }
    fun note(key: String): String = p.getString("note:$key", "") ?: ""
    fun setNote(key: String, v: String) { p.edit().putString("note:$key", v).apply() }
}

@Composable
private fun <T : Any> Remote(path: String, parse: (String) -> T, content: @Composable (T) -> Unit) {
    val state by produceState<Result<T>?>(initialValue = null, path) {
        value = withContext(Dispatchers.IO) { runCatching { parse(httpGet(path)) } }
    }
    val r = state
    if (r == null) {
        Box(Modifier.fillMaxWidth().padding(16.dp)) { CircularProgressIndicator() }
    } else {
        val v = r.getOrNull()
        if (v != null) content(v)
        else Column(Modifier.padding(16.dp)) {
            Text("Dati non raggiungibili", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.titleMedium)
            Text(r.exceptionOrNull()?.message ?: "Errore")
        }
    }
}

// ---------- modelli e lettura JSON ----------
private fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }
private fun <T> JSONArray.mapObjects(f: (JSONObject) -> T): List<T> = (0 until length()).map { f(getJSONObject(it)) }

internal data class Vision(
    val sectorId: String, val sectorName: String, val topic: String, val headline: String,
    val confidence: String, val generatedBy: String, val facts: List<String>, val hypotheses: List<String>,
    val scenarios: List<Pair<String, String>>, val limits: String, val sources: List<Pair<String, String>>,
)
internal data class Day(val date: String, val generatedBy: String, val visions: List<Vision>)

private fun parseDay(text: String): Day {
    val j = JSONObject(text)
    return Day(j.getString("date"), j.optString("generated_by", "regole"), j.getJSONArray("visions").mapObjects { o ->
        Vision(
            o.getString("sector_id"), o.getString("sector_name"), o.getString("topic"), o.getString("headline"),
            o.optString("confidence", "bassa"), o.optString("generated_by", "regole"),
            o.getJSONArray("facts").strings(), o.getJSONArray("hypotheses").strings(),
            o.getJSONArray("scenarios").mapObjects { s -> s.getString("label") to s.getString("text") },
            o.optString("limits", ""),
            o.getJSONArray("sources").mapObjects { s -> s.getString("title") to s.getString("link") },
        )
    })
}

// ---------- componenti ----------
@Composable
private fun Section(title: String, lines: List<String>) {
    if (lines.isEmpty()) return
    Text(title, style = MaterialTheme.typography.labelLarge)
    lines.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium) }
}

@Composable
private fun VisionCard(v: Vision, store: Store) {
    val key = "${v.sectorId}:${v.topic}"
    var watched by remember { mutableStateOf(key in store.watch()) }
    val uri = LocalUriHandler.current
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(v.sectorName, style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
                TextButton(onClick = { store.toggle(key); watched = !watched }) { Text(if (watched) "★" else "☆") }
            }
            Text(v.headline, style = MaterialTheme.typography.titleMedium)
            Text("Affidabilità: ${v.confidence} · scritta da: ${v.generatedBy}", style = MaterialTheme.typography.bodySmall)
            Section("Fatti (dai dati)", v.facts)
            Section("Ipotesi (non certezze)", v.hypotheses)
            Section("Scenari", v.scenarios.map { "${it.first}: ${it.second}" })
            if (v.limits.isNotBlank()) Text("Limiti: ${v.limits}", style = MaterialTheme.typography.bodySmall)
            v.sources.take(4).forEach { (title, link) ->
                TextButton(onClick = { runCatching { uri.openUri(link) } }, contentPadding = PaddingValues(0.dp)) {
                    Text("Fonte: $title", maxLines = 2, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun DayList(day: Day, store: Store, header: String) {
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text(header, style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 16.dp)) }
        item { Text("Aggiornate il ${day.date} · generate da: ${day.generatedBy}", style = MaterialTheme.typography.bodySmall) }
        items(day.visions) { VisionCard(it, store) }
        item { Spacer(Modifier.height(16.dp)) }
    }
}

// ---------- schermate ----------
@Composable
internal fun VisionsScreen() {
    val store = remember { Store(LocalContext.current.applicationContext) }
    Remote("visions/latest.json", ::parseDay) { DayList(it, store, "Visioni di oggi") }
}

@Composable
internal fun WatchlistScreen() {
    val store = remember { Store(LocalContext.current.applicationContext) }
    val keys = remember { store.watch().sorted() }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text("Watchlist e note", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 16.dp)) }
        if (keys.isEmpty()) item { Text("Nessun argomento salvato. Tocca ☆ su una visione o su un argomento del Radar.") }
        items(keys) { key ->
            var note by remember { mutableStateOf(store.note(key)) }
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(key.substringAfter(':'), style = MaterialTheme.typography.titleMedium)
                    Text(key.substringBefore(':'), style = MaterialTheme.typography.bodySmall)
                    OutlinedTextField(note, { note = it; store.setNote(key, it) }, label = { Text("La tua nota") }, modifier = Modifier.fillMaxWidth())
                }
            }
        }
    }
}

private data class Link(val a: String, val b: String, val count: Int)

@Composable
internal fun LinksScreen() {
    val names = mapOf("ai-tech" to "AI e tecnologia", "operations" to "Industria e Operations", "sport" to "Sport e innovazione")
    Remote("links.json", { t ->
        val j = JSONObject(t)
        names.keys.associateWith { s -> if (j.has(s)) j.getJSONArray(s).mapObjects { Link(it.getString("a"), it.getString("b"), it.getInt("count")) } else emptyList() }
    }) { data ->
        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Collegamenti tra argomenti", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 16.dp)) }
            item { Text("Quante notizie, negli ultimi 90 giorni, citano due argomenti insieme.", style = MaterialTheme.typography.bodySmall) }
            data.forEach { (sector, list) ->
                item { Text(names[sector] ?: sector, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp)) }
                if (list.isEmpty()) item { Text("Ancora nessun collegamento: servono più notizie.", style = MaterialTheme.typography.bodySmall) }
                val max = (list.maxOfOrNull { it.count } ?: 1).coerceAtLeast(1)
                items(list.take(10)) { l ->
                    Column {
                        Text("${l.a} ⇄ ${l.b}  (${l.count})")
                        LinearProgressIndicator(progress = { l.count.toFloat() / max }, modifier = Modifier.fillMaxWidth())
                    }
                }
            }
            item { Spacer(Modifier.height(16.dp)) }
        }
    }
}

private data class Verified(val date: String, val topic: String, val horizon: Int, val outcome: String, val hit: Boolean)
private data class Verification(val checked: Int, val confirmed: Int, val items: List<Verified>)
private data class IndexRow(val date: String, val headlines: List<String>)

@Composable
internal fun ArchiveScreen() {
    val store = remember { Store(LocalContext.current.applicationContext) }
    var selected by remember { mutableStateOf<String?>(null) }
    val sel = selected
    if (sel != null) {
        Column(Modifier.fillMaxSize()) {
            TextButton(onClick = { selected = null }, modifier = Modifier.padding(start = 8.dp, top = 8.dp)) { Text("← Archivio") }
            Remote("visions/$sel.json", ::parseDay) { DayList(it, store, "Visioni del $sel") }
        }
        return
    }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { Text("Archivio e verifica", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 16.dp)) }
        item {
            Remote("verification.json", { t ->
                val j = JSONObject(t)
                Verification(j.getInt("checked"), j.getInt("confirmed"), j.getJSONArray("items").mapObjects {
                    Verified(it.getString("date"), it.getString("topic"), it.getInt("horizon_days"), it.getString("outcome"), it.getBoolean("hit"))
                })
            }) { v ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Anticipazioni verificate", style = MaterialTheme.typography.titleMedium)
                        if (v.checked == 0) Text("Nessuna ancora: la prima verifica avviene 30 giorni dopo una visione \"in crescita\".")
                        else {
                            Text("${v.confirmed} confermate su ${v.checked}")
                            if (v.checked < 10) Text("Campione ancora troppo piccolo per giudicare.", style = MaterialTheme.typography.bodySmall)
                            v.items.takeLast(8).reversed().forEach {
                                Text("${if (it.hit) "✔" else "✘"} ${it.topic} · ${it.date} · ${it.horizon}g → ${it.outcome}", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
        }
        item {
            Remote("visions/index.json", { t ->
                val a = JSONArray(t)
                a.mapObjects { IndexRow(it.getString("date"), it.getJSONArray("headlines").strings()) }
            }) { rows ->
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    rows.forEach { r ->
                        Card(Modifier.fillMaxWidth().clickable { selected = r.date }) {
                            Column(Modifier.padding(12.dp)) {
                                Text(r.date, style = MaterialTheme.typography.titleSmall)
                                r.headlines.take(3).forEach { Text("• $it", style = MaterialTheme.typography.bodySmall, maxLines = 1) }
                            }
                        }
                    }
                }
            }
        }
    }
}

// ---------- navigazione ----------
@Composable
internal fun Root() {
    var tab by remember { mutableIntStateOf(0) }
    val tabs = listOf("✦" to "Visioni", "◎" to "Radar", "＋" to "Sezioni", "★" to "Watch", "⇄" to "Mappa", "▤" to "Archivio")
    Scaffold(bottomBar = {
        NavigationBar {
            tabs.forEachIndexed { i, (icon, label) ->
                NavigationBarItem(selected = tab == i, onClick = { tab = i }, icon = { Text(icon) }, label = { Text(label, maxLines = 1, style = MaterialTheme.typography.labelSmall) })
            }
        }
    }) { pad ->
        Box(Modifier.fillMaxSize().padding(pad)) {
            when (tab) {
                0 -> VisionsScreen()
                1 -> RadarApp()
                2 -> SectionsScreen()
                3 -> WatchlistScreen()
                4 -> LinksScreen()
                else -> ArchiveScreen()
            }
        }
    }
}
